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
		taxes_and_charges = frappe.db.get_value("Sales Order", self.no_kontrak, "taxes_and_charges")
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
				"title"    : ["like", taxes_and_charges],
				"disabled" : 0,
			},
			"name"
		)

		if not template_name:
			frappe.throw(
				f"Sales Taxes and Charges Template {taxes_and_charges} "
				f"tidak ditemukan untuk Company <b>{self.company}</b>"
			)

		# Ambil baris tax dari template tersebut
		taxes = frappe.get_all(
			"Sales Taxes and Charges",
			filters={
				"parent"    : template_name,
				"parenttype": "Sales Taxes and Charges Template",
			},
			fields=["tax_amount", "account_head", "rate", "included_in_print_rate"]
		)

		ppn_amount  = 0
		ppn_account = None

		for tax in taxes:
			# Hitung tax_amount dari rate jika tax_amount = 0
			if tax.included_in_print_rate:
				base_amount = self.nilai_dp / (1 + tax.rate / 100)
				amount = self.nilai_dp - base_amount
			else:
				amount = tax.tax_amount or (self.nilai_dp * tax.rate / 100)

			ppn_amount  += amount
			ppn_account  = tax.account_head

		if not ppn_account and ppn_amount > 0:
			frappe.throw("Account PPN tidak ditemukan di Sales Taxes and Charges.")

		if taxes and taxes[0].included_in_print_rate:
			total_amount = self.nilai_dp 
		else:
			total_amount = self.nilai_dp + ppn_amount

		pe = frappe.new_doc("Payment Entry")
		pe.payment_type     = "Receive"
		pe.posting_date     = nowdate()
		pe.party_type       = "Customer"
		pe.party            = customer
		pe.company			= self.company
		pe.unit				= self.unit
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
		# ── 1. Cari linked SI names ────────────────────────────────────────
		linked_si_names = frappe.db.sql("""
			SELECT DISTINCT si.name
			FROM `tabSales Invoice` si
			INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
			INNER JOIN `tabDelivery Note Item` dni ON dni.parent = sii.delivery_note
			INNER JOIN `tabDelivery Order Item` doi ON doi.name = dni.delivery_order_item
			INNER JOIN `tabDelivery Order` tdo ON tdo.name = doi.parent
			WHERE tdo.sales_order = %(no_kontrak)s
			  AND si.docstatus = 1
			  AND si.jenis_penagihan = 'Pengiriman'
		""", {"no_kontrak": self.no_kontrak}, pluck=True)

		if not linked_si_names:
			linked_si_names = frappe.db.sql("""
				SELECT DISTINCT si.name
				FROM `tabSales Invoice` si
				INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
				WHERE sii.sales_order = %(no_kontrak)s
				  AND si.docstatus = 1
				  AND si.jenis_penagihan = 'Pengiriman'
			""", {"no_kontrak": self.no_kontrak}, pluck=True)

		if not linked_si_names:
			frappe.throw(
				f"Tidak ada Sales Invoice Pengiriman yang linked ke kontrak <b>{self.no_kontrak}</b>"
			)

		# ── 2. Cek tax SO: including atau excluding ────────────────────────
		so = frappe.get_doc("Sales Order", self.no_kontrak)

		tax_included = any(t.included_in_print_rate for t in so.get("taxes", []))

		# Hitung divisor dan ppn_rate dari SO
		divisor   = 1.0
		ppn_rate  = 0.0
		ppn_account = None

		for t in so.get("taxes", []):
			if t.included_in_print_rate:
				divisor  *= (1 + t.rate / 100)
				ppn_rate += t.rate
				if not ppn_account:
					ppn_account = t.account_head

		if not tax_included:
			# Excluding: ambil dari template Excluding PPN
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
				fields=["rate", "account_head"]
			)
			if not ppn_tax_rows:
				frappe.throw("Tidak ada baris tax di template Excluding PPN.")

			ppn_rate    = ppn_tax_rows[0].rate
			ppn_account = ppn_tax_rows[0].account_head

		if not ppn_account:
			frappe.throw("Akun PPN tidak ditemukan dari Sales Order maupun template.")

		# ── 3. Ambil SI details ────────────────────────────────────────────
		si_details = frappe.get_all(
			"Sales Invoice",
			filters={"name": ["in", linked_si_names]},
			fields=["name", "customer", "posting_date", "net_total", "grand_total", "debit_to"]
		)

		# ── 4. Build map periode → reclass rows dari child table ──────────
		# Periode di child table format "Januari 2024", cocokkan ke bulan_key "2024-01"
		from frappe.utils import getdate, get_last_day
		import locale

		def periode_to_key(periode_str):
			"""Konversi 'Januari 2024' → '2024-01'"""
			try:
				import datetime
				# Coba parse pakai locale Indonesia
				bulan_map = {
					"januari": 1, "februari": 2, "maret": 3, "april": 4,
					"mei": 5, "juni": 6, "juli": 7, "agustus": 8,
					"september": 9, "oktober": 10, "november": 11, "desember": 12
				}
				parts      = periode_str.lower().split()
				month_num  = bulan_map.get(parts[0], 0)
				year       = int(parts[1])
				return f"{year}-{str(month_num).zfill(2)}"
			except Exception:
				return None

		reclass_by_periode = {}
		for r in self.get("reclass_pengakuan_penjualan", []):
			key = periode_to_key(r.periode)
			if key:
				reclass_by_periode[key] = r

		# ── 5. Group SI per bulan ──────────────────────────────────────────
		from collections import defaultdict

		si_per_bulan = defaultdict(list)
		for si in si_details:
			bulan_key = getdate(si.posting_date).strftime("%Y-%m")
			si_per_bulan[bulan_key].append(si)

		created_si_list = []

		for bulan_key, si_group in sorted(si_per_bulan.items()):

			reclass_row = reclass_by_periode.get(bulan_key)
			if reclass_row:
				total_dpp   = sum(si.net_total for si in si_group)
				total_ppn   = reclass_row.ppn

				if total_ppn <= 0:
					continue

				sample_date  = getdate(si_group[0].posting_date)
				posting_date = get_last_day(sample_date)
				customer     = si_group[0].customer
				debit_to     = si_group[0].debit_to

				# ── Buat Sales Invoice PPN ─────────────────────────────────────
				si_ppn = frappe.new_doc("Sales Invoice")
				si_ppn.customer        = customer
				si_ppn.company         = self.company
				si_ppn.posting_date    = posting_date
				si_ppn.due_date        = posting_date
				si_ppn.no_kontrak_eksternal = frappe.get_doc("Sales Order", self.no_kontrak).no_kontrak_external
				si_ppn.unit		       = self.unit
				si_ppn.set_posting_time = 1
				si_ppn.debit_to        = debit_to
				si_ppn.jenis_penagihan = "Pemenuhan Kontrak"
				si_ppn.keterangan 	   = "PPN + Reclass Nota Piutang {}".format(self.name)
				si_ppn.nota_hutang_pk  = self.name

				# Item placeholder (rate 0, PPN di-handle lewat tax actual)
				si_ppn.append("items", {
					"item_code"   : self.master_barang_placeholder_ppn,
					"qty"         : 1,
					"rate"        : 0,
					"sales_order" : self.no_kontrak,
				})

				# Tax PPN actual
				si_ppn.append("taxes", {
					"charge_type" : "Actual",
					"account_head": ppn_account,
					"description" : f"PPN - {bulan_key}",
					"tax_amount"  : total_ppn,
					"total"       : total_ppn,
				})

				# ── Tambah baris reclass kalau ada ────────────────────────────
				if reclass_row and reclass_row.akun_reclass:
					si_ppn.append("taxes", {
						"charge_type" : "Actual",
						"account_head": reclass_row.akun_reclass,
						"description" : f"Reclass - {reclass_row.periode}",
						"tax_amount"  : reclass_row.reclass,
						"total"       : reclass_row.reclass,
					})

				

				si_ppn.insert(ignore_permissions=True)
				frappe.flags.skip_validate_file = True
				si_ppn.submit()
				created_si_list.append(si_ppn.name)

				for baris_reclass in self.reclass_pengakuan_penjualan:
					if baris_reclass.name == reclass_row.name:
						baris_reclass.pengakuan_penjualan_ppn = si_ppn.name
						baris_reclass.db_update()

		if created_si_list:
			frappe.msgprint(
				f"Sales Invoice PPN berhasil dibuat: <b>{', '.join(created_si_list)}</b>",
				alert=True
			)
		else:
			frappe.msgprint("Tidak ada PPN yang perlu dibuat.", alert=True)
			
	
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
			# Cancel SI PPN
			si_ppn = frappe.get_doc("Sales Invoice", si_name)
			si_ppn.cancel()

			frappe.msgprint(
				f"Sales Invoice PPN <b>{si_name}</b> berhasil di-cancel.",
				alert=True
			)



@frappe.whitelist()
def get_si_pengiriman(no_kontrak):
	def run_query(where_clause, join_clause=""):
		return frappe.db.sql(f"""
			SELECT 
				si.name,
				si.posting_date,
				SUM(COALESCE(NULLIF(sii.qty_timbang_customer, 0), sii.qty)) AS qty,
				sii.rate / COALESCE(
					NULLIF((
						SELECT EXP(SUM(LOG(1 + stc.rate / 100)))
						FROM `tabSales Taxes and Charges` stc
						WHERE stc.parent = si.name
						  AND stc.included_in_print_rate = 1
					), 0),
				1) AS rate,
				SUM(
					COALESCE(NULLIF(sii.qty_timbang_customer, 0), sii.qty) *
					sii.rate / COALESCE(
						NULLIF((
							SELECT EXP(SUM(LOG(1 + stc.rate / 100)))
							FROM `tabSales Taxes and Charges` stc
							WHERE stc.parent = si.name
							  AND stc.included_in_print_rate = 1
						), 0),
					1)
				) AS subtotal
			FROM `tabSales Invoice` si
			JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
			{join_clause}
			WHERE {where_clause}
			  AND si.docstatus = 1
			  AND si.jenis_penagihan = 'Pengiriman'
			GROUP BY si.name, si.posting_date, sii.rate
		""", {"no_kontrak": no_kontrak}, as_dict=1)

	result = run_query(
		where_clause="tdo.sales_order = %(no_kontrak)s",
		join_clause="""
			JOIN `tabDelivery Note Item` dni ON dni.parent = sii.delivery_note
			JOIN `tabDelivery Order Item` doi ON doi.name = dni.delivery_order_item
			JOIN `tabDelivery Order` tdo ON tdo.name = doi.parent
		"""
	)
	if not result:
		result = run_query(where_clause="sii.sales_order = %(no_kontrak)s")

	return result or []

@frappe.whitelist()
def get_nilai_kontrak(no_kontrak):
	# Ambil Sales Order
	so = frappe.get_doc("Sales Order", no_kontrak)

	# Cek apakah tax included_in_print_rate
	tax_included = any(
		t.included_in_print_rate for t in so.get("taxes", [])
	)

	# Hitung divisor dari SO (product semua tax yang included)
	divisor = 1.0
	for t in so.get("taxes", []):
		if t.included_in_print_rate:
			divisor *= (1 + t.rate / 100)

	# Hitung tax rate total dari SO (untuk sisa_ppn)
	tax_rate_total = divisor - 1  # misal 1.11 - 1 = 0.11

	# nilai_kontrak
	nilai_kontrak = so.grand_total

	# dpp
	if tax_included:
		dpp = so.net_total
	else:
		dpp = so.total  # before tax

	# Ambil semua Nota Piutang tipe DP untuk no_kontrak ini
	nota_dp_list = frappe.db.sql("""
		SELECT np.nilai_dp, np.no_kontrak
		FROM `tabNota Piutang` np
		WHERE np.no_kontrak = %(no_kontrak)s
		  AND np.tipe = 'Nota DP'
		  AND np.docstatus = 1
	""", {"no_kontrak": no_kontrak}, as_dict=1)

	# dp_dpp: kalau included, bagi divisor
	dp_dpp_raw = sum(r.nilai_dp or 0 for r in nota_dp_list)
	if tax_included:
		dp_dpp = dp_dpp_raw / divisor
	else:
		dp_ddd = dp_dpp_raw
		dp_dpp = dp_dpp_raw

	# ppn
	ppn = nilai_kontrak - dpp

	# dp_ppn
	dp_ppn = dp_dpp_raw - dp_dpp  # selisih gross dan net dp

	return {
		"nilai_kontrak": nilai_kontrak,
		"dpp": dpp,
		"ppn": ppn,
		"dp_dpp": dp_dpp,
		"dp_ppn": dp_ppn,
		"tax_rate_total": tax_rate_total,  # dikirim ke JS untuk hitung sisa_ppn di client
	}

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_akun_reclass(doctype, txt, searchfield, start, page_len, filters):
	company = filters.get("company") if filters else None
	return frappe.db.sql("""
		SELECT name, account_name
		FROM `tabAccount`
		WHERE is_group = 0
		  AND company = %(company)s
		  AND (name LIKE %(txt)s OR account_name LIKE %(txt)s)
		ORDER BY name
		LIMIT %(start)s, %(page_len)s
	""", {
		"company":  company,
		"txt":      f"%{txt}%",
		"start":    start,
		"page_len": page_len,
	})