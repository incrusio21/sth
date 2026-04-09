import frappe
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice
from frappe.utils import get_last_day

class SalesInvoice(SalesInvoice):
	def on_submit(self):
		super().on_submit()
		if self.jenis_penagihan == "Pengiriman":
			self.create_timbang_journal_entry()
			self.create_dp_payment_journal_entry()

	def on_cancel(self):
		if self.jenis_penagihan == "Pengiriman":
			self.cancel_timbang_journal_entry()
			self.cancel_dp_payment_journal_entry()		
		super().on_cancel()

	def get_gl_entries(self, warehouse_account=None):
		self._apply_timbang_qty()
		gl_entries = super().get_gl_entries(warehouse_account)
		self._restore_original_qty()
		return gl_entries

	def _apply_timbang_qty(self):
		self._original_values = {}
		self._original_totals = {
			"grand_total"       : self.grand_total,
			"base_grand_total"  : self.base_grand_total,
			"net_total"         : self.net_total,
			"base_net_total"    : self.base_net_total,
			"total"             : self.total,
			"base_total"        : self.base_total,
			"outstanding_amount": self.outstanding_amount,
		}

		total_diff = 0
		for item in self.items:
			timbang = item.qty_timbang_customer
			if timbang and timbang != 0:
				self._original_values[item.name] = {
					"qty"            : item.qty,
					"amount"         : item.amount,
					"base_amount"    : item.base_amount,
					"net_amount"     : item.net_amount,
					"base_net_amount": item.base_net_amount,
				}

				original_amount = item.amount
				new_amount      = timbang * item.rate

				item.qty             = timbang
				item.amount          = new_amount
				item.base_amount     = timbang * item.base_rate
				item.net_amount      = timbang * item.net_rate
				item.base_net_amount = timbang * item.base_net_rate

				total_diff += (new_amount - original_amount)

		# Adjust header totals supaya debit Receivable = credit Income
		self.total              = (self.total or 0) + total_diff
		self.base_total         = (self.base_total or 0) + total_diff
		self.net_total          = (self.net_total or 0) + total_diff
		self.base_net_total     = (self.base_net_total or 0) + total_diff
		self.grand_total        = (self.grand_total or 0) + total_diff
		self.base_grand_total   = (self.base_grand_total or 0) + total_diff
		self.outstanding_amount = (self.outstanding_amount or 0) + total_diff

	def _restore_original_qty(self):
		for item in self.items:
			if item.name in self._original_values:
				original = self._original_values[item.name]
				item.qty             = original["qty"]
				item.amount          = original["amount"]
				item.base_amount     = original["base_amount"]
				item.net_amount      = original["net_amount"]
				item.base_net_amount = original["base_net_amount"]
		self._original_values = {}

		# Restore header totals
		for field, value in self._original_totals.items():
			setattr(self, field, value)
		self._original_totals = {}

	def create_timbang_journal_entry(self):
		timbang_items = [
			item for item in self.items
			if item.qty_timbang_customer and item.qty_timbang_customer != 0
		]

		if not timbang_items:
			return

		expense_account = frappe.db.get_value(
			"Company", self.company, "default_expense_account"
		)
		if not expense_account:
			frappe.throw(
				f"Default Expense Account belum diset di Company <b>{self.company}</b>"
			)

		dn_names = list(set([
			item.delivery_note
			for item in timbang_items
			if item.delivery_note
		]))

		if not dn_names:
			frappe.throw(
				"Tidak ada Delivery Note yang ter-link di item Sales Invoice ini."
			)

		dn_account_map = {}
		total_gl = 0

		for dn_name in dn_names:
			# Ambil account debit dari GL Entry Delivery Note
			debit_account = frappe.db.get_value(
				"GL Entry",
				{
					"voucher_type": "Delivery Note",
					"voucher_no"  : dn_name,
					"is_cancelled": 0,
					"debit"       : (">", 0),
				},
				"account"
			)
			if not debit_account:
				frappe.throw(
					f"Akun Debit tidak ditemukan di GL Entry Delivery Note <b>{dn_name}</b>"
				)
			dn_account_map[dn_name] = debit_account

			debit_value = frappe.db.get_value(
				"GL Entry",
				{
					"voucher_type": "Delivery Note",
					"voucher_no"  : dn_name,
					"is_cancelled": 0,
					"debit"       : (">", 0),
				},
				"debit"
			)

			total_gl += debit_value

		total_debit = 0
		dn_amount_map = {}
		for item in timbang_items:
			dn = item.delivery_note
			if not dn:
				continue
			amount = item.qty * item.rate
			dn_amount_map[dn] = dn_amount_map.get(dn, 0) + amount
			total_debit += amount


		je = frappe.new_doc("Journal Entry")
		je.voucher_type = "Journal Entry"
		je.posting_date = self.posting_date
		je.company      = self.company
		je.user_remark  = f"Selisih Timbang Customer - {self.name}"
		je.sales_invoice = self.name

		je.append("accounts", {
			"account"                   : expense_account,
			"debit_in_account_currency" : total_gl,
			"credit_in_account_currency": 0,
		})

		for dn_name, amount in dn_amount_map.items():
			je.append("accounts", {
				"account"                   : dn_account_map[dn_name],
				"debit_in_account_currency" : 0,
				"credit_in_account_currency": total_gl,
			})

		je.insert(ignore_permissions=True)
		je.submit()

		frappe.msgprint(
			f"Journal Entry <b>{je.name}</b> berhasil dibuat untuk selisih timbang.",
			alert=True
		)

	def cancel_timbang_journal_entry(self):
		# Cari dari field timbang_journal_entry dulu
		je_name = self.get("timbang_journal_entry")

		# Fallback cari dari user_remark
		if not je_name:
			je_name = frappe.db.get_value(
				"Journal Entry",
				{
					"user_remark": f"Selisih Timbang Customer - {self.name}",
					"docstatus"  : 1
				},
				"name"
			)

		if not je_name:
			frappe.msgprint(
				"Tidak ada Journal Entry timbang yang perlu di-cancel.",
				alert=True
			)
			return

		je = frappe.get_doc("Journal Entry", je_name)
		je.cancel()

		frappe.msgprint(
			f"Journal Entry <b>{je_name}</b> berhasil di-cancel.",
			alert=True
		)

	def create_dp_payment_journal_entry(self):

		dn_names = list(set([
			item.delivery_note
			for item in self.items
			if item.delivery_note
		]))

		if not dn_names:
			return

		# Ambil Delivery Order dari Delivery Note items
		do_names = list(set(frappe.db.sql("""
			SELECT DISTINCT dni.delivery_order_item
			FROM `tabDelivery Note Item` dni
			WHERE dni.parent IN %(dn_names)s
			AND dni.delivery_order_item IS NOT NULL
			AND dni.delivery_order_item != ''
		""", {"dn_names": dn_names}, pluck=True) or []))

		if not do_names:
			return

		# Ambil Sales Order dari Delivery Order items
		so_names = list(set(frappe.db.sql("""
			SELECT DISTINCT doi.sales_order
			FROM `tabDelivery Order Item` dni
			INNER JOIN `tabDelivery Order` doi ON doi.name = dni.parent
			WHERE dni.name IN %(dn_names)s
			AND doi.sales_order IS NOT NULL
			AND doi.sales_order != ''
		""", {"dn_names": do_names}, pluck=True) or []))

		if not so_names:
			return

		nota_dp_list = frappe.get_all(
			"Nota Piutang",
			filters={
				"no_kontrak": ["in", so_names],
				"tipe"      : "Nota DP",
				"docstatus" : 1,
			},
			fields=["name", "no_kontrak", "akun_uang_muka"]
		)
		if not nota_dp_list:
			return

		# Ambil akun_uang_muka (ambil dari Nota Piutang pertama yang ditemukan)
		akun_uang_muka = nota_dp_list[0].akun_uang_muka
		if not akun_uang_muka:
			frappe.throw("akun_uang_muka tidak ditemukan di Nota Piutang DP.")

		# Hitung total DP yang sudah masuk dari PE Nota Piutang DP
		nota_dp_names = [n.name for n in nota_dp_list]
		total_dp_masuk = frappe.db.sql("""
			SELECT IFNULL(SUM(pe.paid_amount), 0)
			FROM `tabPayment Entry` pe
			WHERE pe.reference_no IN %(nota_dp_names)s
			AND pe.docstatus = 1
		""", {"nota_dp_names": nota_dp_names})[0][0]

		if not total_dp_masuk or total_dp_masuk <= 0:
			return

		# Hitung total DP yang sudah dipakai di JE SI sebelumnya
		total_dp_terpakai = frappe.db.sql("""
			SELECT IFNULL(SUM(jea.debit_in_account_currency), 0)
			FROM `tabJournal Entry Account` jea
			INNER JOIN `tabJournal Entry` je ON je.name = jea.parent
			WHERE je.docstatus = 1
			AND je.user_remark LIKE %(remark_pattern)s
			AND jea.account = %(akun_uang_muka)s
		""", {
			"remark_pattern": "Pembayaran DP Sales Invoice - %",
			"akun_uang_muka": akun_uang_muka,
		})[0][0]

		sisa_dp = total_dp_masuk - total_dp_terpakai

		if sisa_dp <= 0:
			# frappe.msgprint(
			# 	"Sisa DP sudah habis, Journal Entry pembayaran DP tidak dibuat.",
			# 	alert=True
			# )
			return
		outstanding_amount = 0
		for row in self.items:
			outstanding_amount += row.qty_timbang_customer * row.rate

		amount = min(sisa_dp, outstanding_amount)
		if sisa_dp > 0 and sisa_dp < outstanding_amount:
			frappe.msgprint( "Qty melebihi dp, harap di buatkan invoice penjualan" )

		# Ambil receivable account dari SI
		receivable_account = self.debit_to
		if not receivable_account:
			frappe.throw("Receivable account (debit_to) tidak ditemukan di Sales Invoice.")

		je = frappe.new_doc("Journal Entry")
		je.voucher_type = "Journal Entry"
		je.posting_date = get_last_day(self.posting_date)
		je.company      = self.company
		je.user_remark  = f"Pembayaran DP Sales Invoice - {self.name}"
		je.sales_invoice = self.name

		# Debit akun uang muka
		je.append("accounts", {
			"account"                   : akun_uang_muka,
			"debit_in_account_currency" : amount,
			"credit_in_account_currency": 0,
			"party_type"                : "Customer",
			"party"                     : self.customer,
		})

		# Credit Receivable (AR)
		je.append("accounts", {
			"account"                   : receivable_account,
			"debit_in_account_currency" : 0,
			"credit_in_account_currency": amount,
			"party_type"                : "Customer",
			"party"                     : self.customer,
			"reference_type"            : "Sales Invoice",
			"reference_name"            : self.name,
		})

		je.insert(ignore_permissions=True)
		je.submit()

		frappe.db.set_value("Sales Invoice", self.name, "dp_journal_entry", je.name)
		frappe.msgprint(
			f"Journal Entry pembayaran DP <b>{je.name}</b> sebesar "
			f"<b>{frappe.format(amount, 'Currency')}</b> berhasil dibuat.",
			alert=True
		)


	def cancel_dp_payment_journal_entry(self):
		je_name = self.get("dp_journal_entry")

		if not je_name:
			je_name = frappe.db.get_value(
				"Journal Entry",
				{
					"user_remark": f"Pembayaran DP Sales Invoice - {self.name}",
					"docstatus"  : 1,
				},
				"name"
			)

		if not je_name:
			return

		je = frappe.get_doc("Journal Entry", je_name)
		je.cancel()

		frappe.msgprint(
			f"Journal Entry DP <b>{je_name}</b> berhasil di-cancel.",
			alert=True
		)

@frappe.whitelist()
def get_bank_cash_account(mode_of_payment, company):
	account = frappe.db.get_value(
		"Mode of Payment Account", {"parent": mode_of_payment, "company": company}, "default_account"
	)
	if not account:
		return {"account": ""}
		# frappe.throw(
		# 	_("Please set default Cash or Bank account in Mode of Payment {0}").format(
		# 		get_link_to_form("Mode of Payment", mode_of_payment)
		# 	),
		# 	title=_("Missing Account"),
		# )
	return {"account": account}