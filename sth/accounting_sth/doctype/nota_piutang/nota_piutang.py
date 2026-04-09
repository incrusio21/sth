# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import nowdate
from frappe.model.document import Document


class NotaPiutang(Document):
	def autoname(self):
		today = nowdate()  # format: YYYY-MM-DD
		month = today[5:7]   # MM
		year = today[:4]     # YYYY
		period = month + year  # "032026"

		if self.tipe == "Nota DP":
			prefix = f"NDP-{period}-"
		elif self.tipe == "Pemenuhan Kontrak":
			prefix = f"PK-{period}-"
		else:
			frappe.throw("Tipe Nota tidak valid")

		self.name = frappe.model.naming.make_autoname(prefix + ".#####")

	def validate(self):
		self.validate_duplikat()

	def validate_duplikat(self):
		if not self.tipe or not self.no_kontrak:
			return

		duplikat = frappe.db.exists(
			"Nota Piutang",
			{
				"tipe": self.tipe,
				"no_kontrak": self.no_kontrak,
				"name": ("!=", self.name),  # exclude dokumen ini sendiri
				"docstatus": ("!=", 2),     # exclude yang sudah cancelled
			}
		)

		if duplikat:
			frappe.throw(
				f"Nota Piutang dengan Tipe <b>{self.tipe}</b> "
				f"dan No. Kontrak <b>{self.no_kontrak}</b> "
				f"sudah ada: <b>{duplikat}</b>",
				title="Duplikat Tidak Diizinkan"
			)

	def on_submit(self):
		if self.tipe == "Nota DP":
			if self.dibuat_dari_payment_voucher == 0:
				self.create_payment_entry()
		if self.tipe == "Pemenuhan Kontrak":
			self.create_ppn_invoices()


	def create_payment_entry(self):
		customer = frappe.db.get_value("Sales Order", self.no_kontrak, "customer")
		if not customer:
			frappe.throw(
				f"Customer tidak ditemukan di Sales Order <b>{self.no_kontrak}</b>"
			)

		# Ambil tax dari Sales Taxes and Charges yang namanya mengandung "Excluding PPN"
		ppn_amount = 0
		ppn_account = None

		template_name = frappe.db.get_value(
			"Sales Taxes and Charges Template",
			{
				"company"  : self.company,
				"title"    : ["like", "%Excluding PPN%"],
				"disabled" : 0,
			},
			"name"
		)

		if not template_name:
			frappe.throw(
				f"Sales Taxes and Charges Template 'Excluding PPN' "
				f"tidak ditemukan untuk Company <b>{self.company}</b>"
			)

		# Ambil baris tax dari template tersebut
		taxes = frappe.get_all(
			"Sales Taxes and Charges",
			filters={
				"parent"    : template_name,
				"parenttype": "Sales Taxes and Charges Template",
			},
			fields=["tax_amount", "account_head", "rate"]
		)

		ppn_amount  = 0
		ppn_account = None

		for tax in taxes:
			# Hitung tax_amount dari rate jika tax_amount = 0
			amount       = tax.tax_amount or (self.nilai_dp * tax.rate / 100)
			ppn_amount  += amount
			ppn_account  = tax.account_head

		if not ppn_account and ppn_amount > 0:
			frappe.throw("Account PPN tidak ditemukan di Sales Taxes and Charges.")

		total_amount = self.nilai_dp + ppn_amount

		pe = frappe.new_doc("Payment Entry")
		pe.payment_type     = "Receive"
		pe.posting_date     = nowdate()
		pe.party_type       = "Customer"
		pe.party            = customer
		pe.company			= self.company
		pe.paid_from        = self.akun_uang_muka
		pe.paid_to          = self.akun_kas_bank
		pe.paid_amount      = total_amount
		pe.received_amount  = total_amount
		pe.reference_no     = self.name
		pe.reference_date   = nowdate()
		pe.apakah_dp_kontrak = 1
		pe.no_kontrak_penjualan = self.no_kontrak
		pe.remarks          = (
			f"Pembayaran dari {self.tipe} - {self.name} "
			f"atas kontrak {self.no_kontrak}"
		)

		# Baris PPN jika ada
		if ppn_amount and ppn_account:
			pe.append("deductions", {
				"account"     : ppn_account,
				"cost_center" : frappe.db.get_value("Company", self.company, "cost_center"),
				"amount"      : ppn_amount * -1,
			})

		pe.insert(ignore_permissions=True)
		pe.submit()

		frappe.db.set_value("Nota Piutang", self.name, "payment_entry", pe.name)
		frappe.msgprint(
			f"Payment Entry <b>{pe.name}</b> berhasil dibuat.",
			alert=True
		)

	def on_cancel(self):

		if self.tipe == "Nota DP":
			self.cancel_payment_entry()

		if self.tipe == "Pemenuhan Kontrak":
			self.cancel_ppn_invoices()

	def cancel_payment_entry(self):
		# Cari PE yang linked ke Nota Piutang ini
		payment_entry = frappe.db.get_value(
			"Payment Entry",
			{
				"reference_no": self.name,
				"docstatus": 1  # hanya yang submitted
			},
			"name"
		)

		if not payment_entry:
			frappe.msgprint(
				"Tidak ada Payment Entry yang perlu di-cancel.",
				alert=True
			)
			return

		pe = frappe.get_doc("Payment Entry", payment_entry)
		pe.cancel()

		frappe.msgprint(
			f"Payment Entry <b>{payment_entry}</b> berhasil di-cancel.",
			alert=True
		)

	def create_ppn_invoices(self):
		# Ambil semua SI Pengiriman atas nama kontrak ini
		si_list = frappe.get_all(
			"Sales Invoice",
			filters={
				"docstatus"       : 1,
				"jenis_penagihan" : "Pengiriman",
			},
			fields=["name", "customer", "company", "posting_date", "debit_to"]
		)

		if not si_list:
			frappe.throw("Tidak ada Sales Invoice Pengiriman yang ditemukan untuk kontrak ini.")

		# Filter SI yang linked ke no_kontrak ini lewat DN → DO → SO
		linked_si_names = frappe.db.sql("""
			SELECT DISTINCT si.name
			FROM `tabSales Invoice` si
			INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
			INNER JOIN `tabDelivery Note Item` dni ON dni.parent = sii.delivery_note
			INNER JOIN `tabDelivery Order Item` doi ON doi.name = dni.delivery_order_item
			INNER JOIN `tabDelivery Order` tdo on tdo.name = doi.parent
			WHERE tdo.sales_order = %(no_kontrak)s
			AND si.docstatus = 1
			AND si.jenis_penagihan = 'Pengiriman'
		""", {"no_kontrak": self.no_kontrak}, pluck=True)

		if not linked_si_names:
			frappe.throw(
				f"Tidak ada Sales Invoice Pengiriman yang linked ke kontrak <b>{self.no_kontrak}</b>"
			)

		# Ambil rate PPN dari template Excluding PPN sesuai company
		template_name = frappe.db.get_value(
			"Sales Taxes and Charges Template",
			{
				"company" : self.company,
				"title"   : ["like", "%Excluding PPN%"],
				"disabled": 0,
			},
			"name"
		)
		if not template_name:
			frappe.throw(
				f"Template Excluding PPN tidak ditemukan untuk Company <b>{self.company}</b>"
			)

		ppn_tax_rows = frappe.get_all(
			"Sales Taxes and Charges",
			filters={
				"parent"    : template_name,
				"parenttype": "Sales Taxes and Charges Template",
			},
			fields=["rate", "account_head", "charge_type", "description"]
		)
		if not ppn_tax_rows:
			frappe.throw("Tidak ada baris tax di template Excluding PPN.")

		ppn_rate = ppn_tax_rows[0].rate
		ppn_account = ppn_tax_rows[0].account_head

		# Ambil SI details yang linked
		si_details = frappe.get_all(
			"Sales Invoice",
			filters={"name": ["in", linked_si_names]},
			fields=["name", "customer", "posting_date", "net_total", "debit_to"]
		)

		# Cek SI mana yang sudah punya SI PPN (hindari duplikat)
		already_billed = frappe.get_all(
			"Sales Invoice",
			filters={
				"docstatus"      : ["!=", 2],
				"jenis_penagihan": "Pemenuhan Kontrak",
				"nota_hutang_pk" : self.name,
			},
			pluck="name"
		)

		# Group SI per bulan (year-month)
		from collections import defaultdict
		from frappe.utils import get_last_day, getdate

		si_per_bulan = defaultdict(list)
		for si in si_details:
			bulan_key = getdate(si.posting_date).strftime("%Y-%m")
			si_per_bulan[bulan_key].append(si)

		created_si_list = []

		for bulan_key, si_group in si_per_bulan.items():
			# Hitung total PPN bulan ini
			total_net = sum(si.net_total for si in si_group)
			total_ppn = round(total_net * ppn_rate / 100)

			if total_ppn <= 0:
				continue

			# Posting date = akhir bulan
			sample_date  = getdate(si_group[0].posting_date)
			posting_date = get_last_day(sample_date)
			customer     = si_group[0].customer
			debit_to     = si_group[0].debit_to

			# Ambil SO dari no_kontrak
			so_name = self.no_kontrak

			# Buat Sales Invoice PPN
			si_ppn = frappe.new_doc("Sales Invoice")
			si_ppn.customer          = customer
			si_ppn.company           = self.company
			si_ppn.posting_date      = posting_date
			si_ppn.due_date          = posting_date
			si_ppn.debit_to          = debit_to
			si_ppn.jenis_penagihan   = "Pemenuhan Kontrak"
			si_ppn.nota_hutang_pk    = self.name  # field link ke Nota Piutang PK

			si_ppn.append("items", {
				"item_code"   : self.master_barang_placeholder_ppn,  # field di Nota Piutang PK
				"qty"         : 1,
				"rate"        : 0,
				"sales_order" : so_name,
			})

			# Tax actual sebesar total PPN bulan ini
			si_ppn.append("taxes", {
				"charge_type"              : "Actual",
				"account_head"             : ppn_account,
				"description"              : f"Excluding PPN - {bulan_key}",
				"tax_amount"               : total_ppn,
				"total"                    : total_ppn,
			})

			si_ppn.insert(ignore_permissions=True)
			frappe.flags.skip_validate_file = True
			si_ppn.submit()

			created_si_list.append(si_ppn.name)

			# Buat JE pembayaran PPN pakai sisa DP PPN
			self._create_ppn_payment_je(si_ppn, total_ppn, debit_to, posting_date)

		if created_si_list:
			frappe.msgprint(
				f"Sales Invoice PPN berhasil dibuat: <b>{', '.join(created_si_list)}</b>",
				alert=True
			)

	def _create_ppn_payment_je(self, si_ppn, ppn_amount, debit_to, posting_date):
		# Ambil akun PPN dari PE Nota Piutang DP yang linked ke kontrak ini
		nota_dp = frappe.db.get_value(
			"Nota Piutang",
			{
				"no_kontrak": self.no_kontrak,
				"tipe"      : "Nota DP",
				"docstatus" : 1,
			},
			["name", "akun_uang_muka"],
			as_dict=True
		)

		if not nota_dp:
			frappe.msgprint(
				"Nota Piutang DP tidak ditemukan, JE pembayaran PPN tidak dibuat.",
				alert=True
			)
			return

		pe_name = frappe.db.get_value(
			"Payment Entry",
			{"reference_no": nota_dp.name, "docstatus": 1},
			"name"
		)

		if not pe_name:
			frappe.msgprint(
				"Payment Entry Nota Piutang DP tidak ditemukan, JE pembayaran PPN tidak dibuat.",
				alert=True
			)
			return
			
		# Ambil akun PPN dari PE Nota Piutang DP
		ppn_account_dp = frappe.db.get_value(
			"Payment Entry Deduction",
			{"parent": pe_name, "parenttype": "Payment Entry"},
			"account",
			order_by="idx asc"
		)

		if not ppn_account_dp:
			frappe.msgprint(
				"Akun deduction tidak ditemukan di Payment Entry Nota Piutang DP.",
				alert=True
			)
			return

		# Hitung sisa DP PPN yang belum terpakai
		total_ppn_dp = frappe.db.sql("""
			SELECT IFNULL(SUM(pe.paid_amount), 0)
			FROM `tabPayment Entry` pe
			INNER JOIN `tabNota Piutang` nh ON nh.name = pe.reference_no
			WHERE nh.no_kontrak = %(no_kontrak)s
			AND nh.tipe = 'Nota DP'
			AND pe.docstatus = 1
		""", {"no_kontrak": self.no_kontrak})[0][0]

		total_ppn_terpakai = frappe.db.sql("""
			SELECT IFNULL(SUM(jea.credit_in_account_currency), 0)
			FROM `tabJournal Entry Account` jea
			INNER JOIN `tabJournal Entry` je ON je.name = jea.parent
			WHERE je.docstatus = 1
			AND je.user_remark LIKE %(remark_pattern)s
			AND jea.account = %(ppn_account)s
		""", {
			"remark_pattern": "Pembayaran PPN Sales Invoice - %",
			"ppn_account"   : ppn_account_dp,
		})[0][0]

		sisa_ppn = total_ppn_dp - total_ppn_terpakai

		if sisa_ppn <= 0:
			frappe.msgprint(
				f"Sisa DP PPN sudah habis untuk SI PPN <b>{si_ppn.name}</b>.",
				alert=True
			)
			return

		amount = min(sisa_ppn, ppn_amount)


		je = frappe.new_doc("Journal Entry")
		je.voucher_type = "Journal Entry"
		je.posting_date = posting_date
		je.company      = self.company
		je.user_remark  = f"Pembayaran PPN Sales Invoice - {si_ppn.name}"

		# Debit akun PPN dari DP
		je.append("accounts", {
			"account"                   : ppn_account_dp,
			"debit_in_account_currency" : amount,
			"credit_in_account_currency": 0,
		})

		# Credit Receivable SI PPN
		je.append("accounts", {
			"account"                   : debit_to,
			"debit_in_account_currency" : 0,
			"credit_in_account_currency": amount,
			"party_type"                : "Customer",
			"party"                     : si_ppn.customer,
			"reference_type"            : "Sales Invoice",
			"reference_name"            : si_ppn.name,
		})

		je.insert(ignore_permissions=True)
		je.submit()

		frappe.db.set_value("Sales Invoice", si_ppn.name, "dp_journal_entry", je.name)
		frappe.msgprint(
			f"JE Pembayaran PPN <b>{je.name}</b> sebesar "
			f"<b>{frappe.format(amount, 'Currency')}</b> berhasil dibuat.",
			alert=True
		)

	def cancel_ppn_invoices(self):
		# Ambil semua SI PPN yang dibuat dari Nota Piutang PK ini
		si_ppn_list = frappe.get_all(
			"Sales Invoice",
			filters={
				"nota_hutang_pk" : self.name,
				"jenis_penagihan": "Pemenuhan Kontrak",
				"docstatus"      : 1,
			},
			pluck="name"
		)

		if not si_ppn_list:
			frappe.msgprint(
				"Tidak ada Sales Invoice PPN yang perlu di-cancel.",
				alert=True
			)
			return

		for si_name in si_ppn_list:
			# Cancel JE pembayaran PPN dulu sebelum cancel SI
			self._cancel_ppn_payment_je(si_name)

			# Cancel SI PPN
			si_ppn = frappe.get_doc("Sales Invoice", si_name)
			si_ppn.cancel()

			frappe.msgprint(
				f"Sales Invoice PPN <b>{si_name}</b> berhasil di-cancel.",
				alert=True
			)

	def _cancel_ppn_payment_je(self, si_name):
		# Cari dari field dp_journal_entry di SI PPN
		je_name = frappe.db.get_value("Sales Invoice", si_name, "dp_journal_entry")

		# Fallback cari dari user_remark
		if not je_name:
			je_name = frappe.db.get_value(
				"Journal Entry",
				{
					"user_remark": f"Pembayaran PPN Sales Invoice - {si_name}",
					"docstatus"  : 1,
				},
				"name"
			)

		if not je_name:
			frappe.msgprint(
				f"Tidak ada JE pembayaran PPN untuk SI <b>{si_name}</b>.",
				alert=True
			)
			return

		je = frappe.get_doc("Journal Entry", je_name)
		je.cancel()

		frappe.msgprint(
			f"Journal Entry PPN <b>{je_name}</b> berhasil di-cancel.",
			alert=True
		)

@frappe.whitelist()
def get_si_pengiriman(no_kontrak):
	si_names = frappe.db.sql("""
		SELECT 
			si.name, 
			SUM(sii.qty_timbang_customer) OR SUM(sii.qty) as qty, 
			sii.rate, 
			SUM(sii.rate*sii.qty_timbang_customer) OR SUM(sii.rate*sii.qty) as subtotal
		FROM `tabSales Invoice` si
		JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		JOIN `tabDelivery Note Item` dni ON dni.parent = sii.delivery_note
		JOIN `tabDelivery Order Item` doi ON doi.name = dni.delivery_order_item
		JOIN `tabDelivery Order` tdo on tdo.name = doi.parent
		WHERE tdo.sales_order = %(no_kontrak)s
		AND si.docstatus = 1
		AND si.jenis_penagihan = 'Pengiriman'
		GROUP BY si.name
	""", {"no_kontrak": no_kontrak}, as_dict=1)

	if not si_names:
		return []

	return si_names