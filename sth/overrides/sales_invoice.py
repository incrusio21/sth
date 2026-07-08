import frappe
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice
from frappe.utils import get_last_day,flt

class SalesInvoice(SalesInvoice):
	def validate(self):
		if self.is_return == 1:
			for row in self.items:
				if row.qty > 0:
					row.qty = row.qty * -1
				if row.qty_timbang_customer > 0:
					row.qty_timbang_customer = row.qty_timbang_customer * -1

		self.hitung_do_tidak_terkirim()
		if self.jenis_penagihan == "Pengiriman":
			self._apply_timbang_qty_tanpa_ganti()

	def on_submit(self):
		super().on_submit()
		if self.jenis_penagihan == "Pengiriman" and self.is_return == 0:
			self.create_timbang_journal_entry()
			self.create_dp_payment_journal_entry()

	def on_cancel(self):
		if self.jenis_penagihan == "Pengiriman" and self.is_return == 0:
			try:
				self.cancel_timbang_journal_entry()
				self.cancel_dp_payment_journal_entry()		
			except:
				pass
		super().on_cancel()

	def get_gl_entries(self, warehouse_account=None):
		if self.jenis_penagihan == "Pengiriman":
			self._apply_timbang_qty()

		gl_entries = super().get_gl_entries(warehouse_account)
		# frappe.throw("{}-{}-{}".format(self.grand_total, self.base_grand_total, self,total_akhir_timbang))
		if self.jenis_penagihan == "Pengiriman":
			self._restore_original_qty()

		return gl_entries

	def hitung_do_tidak_terkirim(self):
		# Ambil semua Sales Order dari item invoice
		sales_orders = list(set([
			item.sales_order for item in self.items 
			if item.get("sales_order")
		]))

		if not sales_orders:
			self.qty_do_belum_terkirim = 0
		else:
			# Total qty dari Delivery Order (submitted) berdasarkan sales order
			do_qty = frappe.db.sql("""
				SELECT COALESCE(SUM(doi.qty), 0)
				FROM `tabDelivery Order Item` doi
				INNER JOIN `tabDelivery Order` do_doc 
					ON do_doc.name = doi.parent
				WHERE doi.against_sales_order IN %(sales_orders)s
				  AND do_doc.docstatus = 1
			""", {"sales_orders": sales_orders})[0][0] or 0

			# Total qty dari Delivery Note (submitted) yang punya delivery_order_item
			dn_qty = frappe.db.sql("""
				SELECT COALESCE(SUM(dni.qty), 0)
				FROM `tabDelivery Note Item` dni
				INNER JOIN `tabDelivery Note` dn 
					ON dn.name = dni.parent
				WHERE dni.against_sales_order IN %(sales_orders)s
				  AND dn.docstatus = 1
			""", {"sales_orders": sales_orders})[0][0] or 0

			self.qty_do_belum_terkirim = flt(do_qty) - flt(dn_qty)
	
	def _apply_timbang_qty_tanpa_ganti(self):
		self._original_values = {}
		self._original_totals = {
			"grand_total"       : self.grand_total,
			"base_grand_total"  : self.base_grand_total,
			"net_total"         : self.net_total,
			"base_net_total"    : self.base_net_total,
			"total"             : self.total,
			"base_total"        : self.base_total,
			"outstanding_amount": self.outstanding_amount,
			"taxes"             : [
				{
					"name"         : t.name,
					"tax_amount"   : t.tax_amount,
					"total"        : t.total,
					"base_total"   : t.base_total,
					"tax_amount_after_discount_amount": t.tax_amount_after_discount_amount,
				}
				for t in self.taxes
			],
		}
		so_name = None
		for item in self.items:
			if item.so_detail:
				so_name = frappe.db.get_value("Sales Order Item", item.so_detail, "parent")
				break  # cukup ambil dari item pertama yang punya so_detail

		has_included_tax = False
		included_tax_rate = 0

		if so_name:
			so_taxes = frappe.get_all(
				"Sales Taxes and Charges",
				filters={"parent": so_name, "parenttype": "Sales Order"},
				fields=["included_in_print_rate", "rate"],
			)
			has_included_tax = any(t.included_in_print_rate for t in so_taxes)
			if has_included_tax:
				for t in so_taxes:
					if t.included_in_print_rate:
						included_tax_rate += t.rate
		else:
			# fallback ke self.taxes jika tidak ada dn_detail sama sekali
			frappe.throw("Sales Order wajib dipasang di Sales Invoice Pengiriman.")
			has_included_tax = any(t.included_in_print_rate for t in self.taxes)
			if has_included_tax:
				for t in self.taxes:
					if t.included_in_print_rate:
						included_tax_rate += t.rate

		total_diff = 0
		total_timbang = 0
		for item in self.items:
			timbang = item.qty_timbang_customer
			if not timbang:
				timbang = item.qty
			
			if timbang and timbang != 0:
				# print(item.rate)
				self._original_values[item.name] = {
					"qty"            : item.qty,
					"rate"           : item.rate,
					"base_rate"      : item.base_rate,
					"net_rate"       : item.net_rate,
					"base_net_rate"  : item.base_net_rate,
					"amount"         : item.amount,
					"base_amount"    : item.base_amount,
					"net_amount"     : item.net_amount,
					"base_net_amount": item.base_net_amount,
				}

				# ── Ambil rate dari DN Item jika dn_detail ada ──────────────
				if item.so_detail:
					so_item_rate      = flt(frappe.db.get_value("Sales Order Item", item.so_detail, "rate") or item.rate)
					so_item_base_rate = flt(frappe.db.get_value("Sales Order Item", item.so_detail, "base_rate") or item.base_rate)
					item.rate      = so_item_rate
					item.base_rate = so_item_base_rate
					item.net_rate      = so_item_rate
					item.base_net_rate = so_item_base_rate

				# ────────────────────────────────────────────────────────────

				original_amount = item.amount
				if has_included_tax:
					divisor         = 1 + (included_tax_rate / 100)
					clean_rate      = flt(so_item_rate / divisor, 9)
					clean_base_rate = flt(so_item_base_rate / divisor, 9)
					# print(clean_rate)
					item.rate           = clean_rate
					item.base_rate      = clean_base_rate
					item.net_rate       = clean_rate
					item.base_net_rate  = clean_base_rate
					new_amount = timbang * clean_rate
					# print(new_amount)

				else:
					new_amount = timbang * item.rate

				# item.qty             = timbang
				item.amount          = item.qty * item.rate
				item.base_amount     = item.qty * item.base_rate
				item.net_amount      = item.qty * item.net_rate
				item.base_net_amount = item.qty * item.base_net_rate
				item.sub_total_timbang = new_amount
				total_timbang += new_amount

				self.calculate_taxes_and_totals()
				# total_diff += (new_amount - original_amount)

		if has_included_tax:
			for t in self.taxes:
				t.tax_amount                          = 0
				t.total                               = 0
				t.base_total                          = 0
				t.tax_amount_after_discount_amount    = 0

		self.taxes_and_charges       = ""
		self.taxes                   = []
		self.total_taxes_and_charges = 0
		self.disable_rounded_total = 1
		self.total_akhir_timbang = total_timbang

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
			"taxes"             : [
				{
					"name"         : t.name,
					"tax_amount"   : t.tax_amount,
					"total"        : t.total,
					"base_total"   : t.base_total,
					"tax_amount_after_discount_amount": t.tax_amount_after_discount_amount,
				}
				for t in self.taxes
			],
		}
		so_name = None
		for item in self.items:
			if item.so_detail:
				so_name = frappe.db.get_value("Sales Order Item", item.so_detail, "parent")
				break  # cukup ambil dari item pertama yang punya so_detail

		has_included_tax = False
		included_tax_rate = 0

		if so_name:
			so_taxes = frappe.get_all(
				"Sales Taxes and Charges",
				filters={"parent": so_name, "parenttype": "Sales Order"},
				fields=["included_in_print_rate", "rate"],
			)
			has_included_tax = any(t.included_in_print_rate for t in so_taxes)
			if has_included_tax:
				for t in so_taxes:
					if t.included_in_print_rate:
						included_tax_rate += t.rate
		else:
			# fallback ke self.taxes jika tidak ada dn_detail sama sekali
			frappe.throw("Sales Order wajib dipasang di Sales Invoice Pengiriman.")
			has_included_tax = any(t.included_in_print_rate for t in self.taxes)
			if has_included_tax:
				for t in self.taxes:
					if t.included_in_print_rate:
						included_tax_rate += t.rate

		total_diff = 0
		for item in self.items:
			timbang = item.qty_timbang_customer
			if not timbang:
				timbang = item.qty
			if timbang and timbang != 0:
				self._original_values[item.name] = {
					"qty"            : item.qty,
					"rate"           : item.rate,
					"base_rate"      : item.base_rate,
					"net_rate"       : item.net_rate,
					"base_net_rate"  : item.base_net_rate,
					"amount"         : item.amount,
					"base_amount"    : item.base_amount,
					"net_amount"     : item.net_amount,
					"base_net_amount": item.base_net_amount,
				}

				# ── Ambil rate dari DN Item jika dn_detail ada ──────────────
				if item.so_detail:
					so_item_rate      = flt(frappe.db.get_value("Sales Order Item", item.so_detail, "rate") or item.rate)
					so_item_base_rate = flt(frappe.db.get_value("Sales Order Item", item.so_detail, "base_rate") or item.base_rate)
					item.rate      = so_item_rate
					item.base_rate = so_item_base_rate
					item.net_rate      = so_item_rate
					item.base_net_rate = so_item_base_rate

				# ────────────────────────────────────────────────────────────

				original_amount = item.amount
				if has_included_tax:
					divisor         = 1 + (included_tax_rate / 100)
					clean_rate      = flt(so_item_rate / divisor, 9)
					clean_base_rate = flt(so_item_base_rate / divisor, 9)
					item.rate           = clean_rate
					item.base_rate      = clean_base_rate
					item.net_rate       = clean_rate
					item.base_net_rate  = clean_base_rate
					new_amount = timbang * clean_rate
				else:
					new_amount = timbang * item.rate

				item.qty             = timbang
				item.amount          = new_amount
				item.base_amount     = timbang * item.base_rate
				item.net_amount      = timbang * item.net_rate
				item.base_net_amount = timbang * item.base_net_rate
				item.sub_total_timbang = new_amount
				total_diff += (new_amount - original_amount)
				item.db_update()

		if has_included_tax:
			for t in self.taxes:
				t.tax_amount                          = 0
				t.total                               = 0
				t.base_total                          = 0
				t.tax_amount_after_discount_amount    = 0

		self.taxes_and_charges       = ""
		self.taxes                   = []
		self.total_taxes_and_charges = 0
		self.total              = (self.total or 0) + total_diff
		self.base_total         = (self.base_total or 0) + total_diff
		self.net_total          = (self.net_total or 0) + total_diff
		self.base_net_total     = (self.base_net_total or 0) + total_diff
		# self.grand_total        = (self.grand_total or 0) + total_diff
		self.total_akhir_timbang = (self.grand_total or 0) + total_diff
		self.rounded_total      = (self.rounded_total or 0) + total_diff
		self.base_grand_total   = (self.base_grand_total or 0) + total_diff
		self.outstanding_amount = (self.outstanding_amount or 0) + total_diff
		self.set_total_in_words()
		self.db_update()

	def _restore_original_qty(self):
		for item in self.items:
			if item.name in self._original_values:
				orig = self._original_values[item.name]
				item.qty             = orig["qty"]
				item.rate            = orig["rate"]
				item.base_rate       = orig["base_rate"]
				item.net_rate        = orig["net_rate"]
				item.base_net_rate   = orig["base_net_rate"]
				item.amount          = orig["amount"]
				item.base_amount     = orig["base_amount"]
				item.net_amount      = orig["net_amount"]
				item.base_net_amount = orig["base_net_amount"]

		for key in ["total", "base_total", "net_total", "base_net_total"]:
			setattr(self, key, self._original_totals[key])

	def create_timbang_journal_entry(self):
		timbang_items = [
			item for item in self.items
		]

		if not timbang_items:
			return

		# expense_account = frappe.db.get_value(
		# 	"Company", self.company, "default_expense_account"
		# )
		# if not expense_account:
		# 	frappe.throw(
		# 		f"Default Expense Account belum diset di Company <b>{self.company}</b>"
		# 	)

		expense_account = self.items[0].income_account

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

		# for dn_name, amount in dn_amount_map.items():
		# 	je.append("accounts", {
		# 		"account"                   : dn_account_map[dn_name],
		# 		"debit_in_account_currency" : 0,
		# 		"credit_in_account_currency": total_gl,
		# 	})

		for dn_name, amount in dn_amount_map.items():
			je.append("accounts", {
				"account"                   : dn_account_map[dn_name],
				"debit_in_account_currency" : 0,
				"credit_in_account_currency": total_gl,
			})
			break

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
			
		else:
			je = frappe.get_doc("Journal Entry", je_name)
			if je.docstatus == 1:
				je.cancel()

				frappe.msgprint(
					f"Journal Entry <b>{je_name}</b> berhasil di-cancel.",
					alert=True
				)

	def create_dp_payment_journal_entry(self):

		so_names = []

		for row in self.items:
			if row.sales_order:
				so_names.append(row.sales_order)

		if len(so_names) == 0:

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
			SELECT IFNULL(SUM(pe.unallocated_amount), 0)
			FROM `tabPayment Entry` pe
			WHERE pe.reference_no IN %(nota_dp_names)s
			AND pe.docstatus = 1
		""", {"nota_dp_names": nota_dp_names})[0][0]

		if not total_dp_masuk or total_dp_masuk <= 0:
			return

		so_doc = frappe.get_doc("Sales Order", self.items[0].sales_order)

		has_included_tax = any(t.included_in_print_rate for t in so_doc.taxes)
		included_tax_rate = 0
		if has_included_tax:
			for t in so_doc.taxes:
				if t.included_in_print_rate:
					included_tax_rate += t.rate
		divisor = 1 + (included_tax_rate / 100)

		# Hitung total DP yang sudah dipakai di JE SI sebelumnya
		total_dp_terpakai = frappe.db.sql("""
			SELECT IFNULL(SUM(jea.debit_in_account_currency), 0)
			FROM `tabJournal Entry Account` jea
			INNER JOIN `tabJournal Entry` je ON je.name = jea.parent
			WHERE je.docstatus = 1
			AND je.user_remark LIKE %(remark_pattern)s
			AND jea.account = %(akun_uang_muka)s
			AND je.sales_order IN %(so_names)s
		""", {
			"remark_pattern": "Pembayaran DP Sales Invoice - %",
			"akun_uang_muka": akun_uang_muka,
			"so_names": so_names
		})[0][0]

		if has_included_tax:
			# frappe.throw("{}-{}-{}-{}".format(total_dp_masuk, divisor, flt(total_dp_masuk / divisor,9), total_dp_terpakai))
			total_dp_masuk = flt(total_dp_masuk / divisor,9)

		sisa_dp = total_dp_masuk - total_dp_terpakai

		# frappe.throw(str(total_dp_masuk))

		if sisa_dp <= 0:
			# frappe.msgprint(
			# 	"Sisa DP sudah habis, Journal Entry pembayaran DP tidak dibuat.",
			# 	alert=True
			# )
			return
		outstanding_amount = 0

		for row in self.items:

			# if has_included_tax:
			# 	clean_rate      = flt(row.rate / divisor, 9)
			# else:
			# 	clean_rate 		= flt(row.rate, 9)

			qty_check = row.qty
			if row.qty_timbang_customer:
				qty_check = row.qty_timbang_customer

			outstanding_amount += qty_check * row.rate

		amount = min(sisa_dp, flt(outstanding_amount,2))

		if sisa_dp < outstanding_amount:
			frappe.msgprint( "Qty melebihi dp, harap dibuatkan invoice penjualan." )
		elif sisa_dp <= 0:
			frappe.msgprint( "DP sudah habis, harap dibuatkan invoice penjualan.")

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
		je.sales_order = so_names[0]

		# Debit akun uang muka
		je.append("accounts", {
			"account"                   : akun_uang_muka,
			"debit_in_account_currency" : amount,
			"debit"						: amount,
			"credit_in_account_currency": 0,
			"credit"					: 0,
			"party_type"                : "Customer",
			"party"                     : self.customer,
		})

		# Credit Receivable (AR)
		je.append("accounts", {
			"account"                   : receivable_account,
			"debit_in_account_currency" : 0,
			"debit"						: 0,
			"credit_in_account_currency": amount,
			"credit"					: amount,
			"party_type"                : "Customer",
			"party"                     : self.customer,
			"reference_type"            : "Sales Invoice",
			"reference_name"            : self.name,
		})
		je.total_amount = amount
		if je.total_amount > 1:
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
			pass
			# return
		else:
			je = frappe.get_doc("Journal Entry", je_name)
			if je.docstatus == 1:
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