# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import nowdate, flt
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

		if self.tipe == "Nota DP":
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
		pe.nota_piutang_pemenuhan_kontrak = self.name
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
		linked_si_names = [
			row.pengakuan_penjualan
			for row in self.get("nota_hutang_pemenuhan_kontrak_table", [])
			if row.pengakuan_penjualan
		]

		if not linked_si_names:
			frappe.throw(
				f"Tidak ada Sales Invoice di tabel Pemenuhan Kontrak pada dokumen ini."
			)

		# ── 2. Cek tax SO: including atau excluding ────────────────────────
		so = frappe.get_doc("Sales Order", self.no_kontrak)
		tax_included = any(t.included_in_print_rate for t in so.get("taxes", []))

		ppn_rate    = 0.0
		ppn_account = None

		if tax_included:
			for t in so.get("taxes", []):
				if t.included_in_print_rate:
					ppn_rate += t.rate
					if not ppn_account:
						ppn_account = t.account_head
		else:
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
		from frappe.utils import getdate, get_last_day

		def periode_to_key(periode_str):
			try:
				bulan_map = {
					"januari": 1, "februari": 2, "maret": 3, "april": 4,
					"mei": 5, "juni": 6, "juli": 7, "agustus": 8,
					"september": 9, "oktober": 10, "november": 11, "desember": 12
				}
				parts     = periode_str.lower().split()
				month_num = bulan_map.get(parts[0], 0)
				year      = int(parts[1])
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

		created_je_list = []

		for bulan_key, si_group in sorted(si_per_bulan.items()):
			reclass_row = reclass_by_periode.get(bulan_key)
			if not reclass_row:
				continue

			total_ppn = reclass_row.ppn
			if total_ppn <= 0:
				continue

			sample_date  = getdate(si_group[0].posting_date)
			posting_date = get_last_day(sample_date)
			customer     = si_group[0].customer
			debit_to     = si_group[0].debit_to  # akun piutang

			# ── Buat Journal Entry ─────────────────────────────────────────
			je = frappe.new_doc("Journal Entry")
			je.voucher_type    = "Journal Entry"
			je.company         = self.company
			je.posting_date    = posting_date
			je.user_remark     = f"PPN + Reclass Nota Piutang {self.name} - {bulan_key}"
			je.sales_order     = self.no_kontrak
			je.nota_hutang_pk  = self.name  # custom field, sesuaikan jika nama berbeda

			# Baris 1: Debit piutang (akun AR customer) sebesar PPN
			je.append("accounts", {
				"account"       : debit_to,
				"party_type"    : "Customer",
				"party"         : customer,
				"debit_in_account_currency" : total_ppn,
				"credit_in_account_currency": 0,
				"user_remark"   : f"PPN {bulan_key}",
			})

			# Baris 2: Credit akun PPN keluaran
			je.append("accounts", {
				"account"       : ppn_account,
				"debit_in_account_currency" : 0,
				"credit_in_account_currency": total_ppn,
				"user_remark"   : f"PPN {bulan_key}",
			})

			# Baris 3 & 4: Reclass (jika akun reclass tersedia)
			if reclass_row.akun_reclass and reclass_row.reclass:
				total_reclass = reclass_row.reclass

				# Tentukan arah debit/credit reclass sesuai kebutuhan bisnis.
				# Contoh: debit akun reclass, credit kembali ke akun piutang.
				# Sesuaikan pasangan akun ini dengan perlakuan akuntansi yang berlaku.
				je.append("accounts", {
					"account"       : reclass_row.akun_reclass,
					"user_remark"   : f"Reclass {reclass_row.periode}",
					"debit_in_account_currency" : 0,
					"credit_in_account_currency": total_reclass,
				})
				je.append("accounts", {
					"account"       : debit_to,
					"party_type"    : "Customer",
					"party"         : customer,
					"debit_in_account_currency" : total_reclass,
					"credit_in_account_currency": 0,
					"user_remark"   : f"Reclass {reclass_row.periode}",
				})

			je.insert(ignore_permissions=True)
			je.submit()
			created_je_list.append(je.name)

			# Update child table dengan referensi JE
			for baris_reclass in self.reclass_pengakuan_penjualan:
				if baris_reclass.name == reclass_row.name:
					baris_reclass.pengakuan_penjualan_ppn = je.name
					baris_reclass.db_update()

		if created_je_list:
			frappe.msgprint(
				f"Journal Entry PPN berhasil dibuat: <b>{', '.join(created_je_list)}</b>",
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
def get_si_pengiriman(no_kontrak, bulan=None):
	"""
	Ambil SI Pengiriman untuk kontrak, exclude:
	1. SI yang sudah ada di Nota Piutang lain (docstatus != 2)
	2. SI yang sudah di-offset DP lewat Journal Entry (je.sales_invoice = si.name)
	   → tapi hanya exclude kalau outstanding_amount - total_offset <= 0
	3. Filter per bulan posting_date kalau bulan diisi (format: YYYY-MM)
	"""
	# SI yang sudah terpakai di Nota Piutang manapun yang tidak di-cancel
	si_terpakai = frappe.db.sql_list("""
		SELECT DISTINCT child.pengakuan_penjualan
		FROM `tabNota Piutang Pemenuhan Kontrak Table` child
		JOIN `tabNota Piutang` np ON np.name = child.parent
		WHERE np.docstatus != 2
		  AND child.pengakuan_penjualan IS NOT NULL
		  AND child.pengakuan_penjualan != ''
	""")

	# SI yang sudah di-offset DP lewat JE: ambil nama + total amount offset-nya
	si_je_dp_amounts = frappe.db.sql("""
		SELECT je.sales_invoice, SUM(jea.credit) AS total_offset
		FROM `tabJournal Entry` je
		JOIN `tabJournal Entry Account` jea ON jea.parent = je.name
		WHERE je.docstatus = 1
		  AND je.sales_order = %s
		  AND je.sales_invoice IS NOT NULL
		  AND je.sales_invoice != ''
		  AND jea.reference_name = je.sales_invoice
		GROUP BY je.sales_invoice
	""", [no_kontrak], as_dict=True)

	# Map: {si_name: total_offset}
	offset_map = {row.sales_invoice: row.total_offset for row in si_je_dp_amounts}

	conditions   = ["si.docstatus = 1", "sii.sales_order = %s"]
	ordered_vals = [no_kontrak]

	if bulan:
		tahun, bln = bulan.split('-')
		conditions.append("YEAR(si.posting_date) = %s")
		conditions.append("MONTH(si.posting_date) = %s")
		ordered_vals += [int(tahun), int(bln)]

	if si_terpakai:
		placeholders = ', '.join(['%s'] * len(si_terpakai))
		conditions.append(f"si.name NOT IN ({placeholders})")
		ordered_vals += si_terpakai

	where_clause = " AND ".join(conditions)

	query = f"""
		SELECT
			si.name,
			si.posting_date,
			si.grand_total as outstanding_amount,
			sii.qty,
			sii.rate,
			sii.amount AS subtotal
		FROM `tabSales Invoice` si
		JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		WHERE {where_clause}
		ORDER BY si.posting_date
	"""

	rows = frappe.db.sql(query, ordered_vals, as_dict=True)

	# Post-filter: kalau SI ada di offset_map,
	# kurangi outstanding_amount dengan total_offset
	# → exclude kalau sisa <= 0, update field kalau masih ada sisa
	result = []
	for row in rows:
		if row.name in offset_map:
			sisa = row.outstanding_amount - offset_map[row.name]
			if sisa <= 0:
				continue  # sudah lunas dari offset DP, skip
			row.outstanding_amount = sisa  # tampilkan sisa yang belum terbayar
		result.append(row)

	return result
	
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


@frappe.whitelist()
def get_sisa_dp(no_kontrak):
	"""
	Sisa DP = Total DP diterima (Payment Entry) - Total DP terpakai (JE offset di SI Pengiriman)

	DP diterima  : Payment Entry dimana apakah_dp_kontrak=1 dan no_kontrak_penjualan=no_kontrak
	DP terpakai  : Journal Entry dimana sales_order=no_kontrak, 
				   child debit di akun uang muka (akun yang sama dengan field akun_uang_muka 
				   di Nota Piutang tipe Nota DP untuk kontrak ini)
	"""

	# 1. Ambil akun_uang_muka dari Nota Piutang tipe "Nota DP" untuk kontrak ini
	akun_uang_muka = frappe.db.get_value(
		'Nota Piutang',
		{
			'no_kontrak': no_kontrak,
			'tipe': 'Nota DP',
			'docstatus': 1
		},
		'akun_uang_muka'
	)

	if not akun_uang_muka:
		# Belum ada Nota DP submitted untuk kontrak ini, DP = 0
		return 0

	# 2. Total DP yang diterima dari Payment Entry
	dp_diterima = frappe.db.sql("""
		SELECT COALESCE(SUM(pe.paid_amount), 0)
		FROM `tabPayment Entry` pe
		WHERE pe.docstatus = 1
		  AND pe.apakah_dp_kontrak = 1
		  AND pe.no_kontrak_penjualan = %(no_kontrak)s
	""", {'no_kontrak': no_kontrak})[0][0]

	# 3. Total DP yang sudah terpakai (debit akun uang muka di JE yang sales_order = kontrak)
	dp_terpakai = frappe.db.sql("""
		SELECT COALESCE(SUM(jed.debit), 0)
		FROM `tabJournal Entry Account` jed
		JOIN `tabJournal Entry` je ON je.name = jed.parent
		WHERE je.docstatus = 1
		  AND je.sales_order = %(no_kontrak)s
		  AND jed.account = %(akun_uang_muka)s
	""", {
		'no_kontrak': no_kontrak,
		'akun_uang_muka': akun_uang_muka
	})[0][0]

	sisa = flt(dp_diterima) - flt(dp_terpakai)
	return sisa if sisa > 0 else 0

@frappe.whitelist()
def get_dp_from_je(no_kontrak, pengakuan_list):
    import json

    if isinstance(pengakuan_list, str):
        pengakuan_list = json.loads(pengakuan_list)

    if not pengakuan_list:
        return {"dp_dpp": 0, "dp_ppn": 0}

    # ── 1. Ambil tax rate dari Sales Order ──────────────────────────────
    so = frappe.get_doc("Sales Order", no_kontrak)

    tax_rate = 0.0
    for t in so.get("taxes", []):
        tax_rate += t.rate / 100  # e.g. 11% → 0.11

    # ── 2. Cari JE DP yang terkait pengakuan_penjualan ──────────────────
    je_rows = frappe.db.sql("""
        SELECT je.name, je.sales_invoice
        FROM `tabJournal Entry` je
        WHERE je.sales_order   = %(no_kontrak)s
          AND je.user_remark   LIKE %(user_remark)s
          AND je.docstatus     = 1
          AND je.sales_invoice IN %(pengakuan_list)s
    """, {
        "no_kontrak":     no_kontrak,
        "user_remark":    "Pembayaran DP Sales Invoice%",
        "pengakuan_list": tuple(pengakuan_list),
    }, as_dict=1)

    if not je_rows:
        return {"dp_dpp": 0, "dp_ppn": 0}

    # ── 3. Total debit dari JE Account ──────────────────────────────────
    je_names = tuple(j.name for j in je_rows)

    debit_row = frappe.db.sql("""
        SELECT COALESCE(SUM(jea.debit_in_account_currency), 0) AS total_debit
        FROM `tabJournal Entry Account` jea
        WHERE jea.parent IN %(je_names)s
    """, {"je_names": je_names}, as_dict=1)

    total_debit = debit_row[0].total_debit if debit_row else 0

    # ── 4. dp_dpp = total_debit, dp_ppn = dp_dpp * rate ─────────────────
    dp_dpp = total_debit
    dp_ppn = dp_dpp * tax_rate

    return {
        "dp_dpp": dp_dpp,
        "dp_ppn": dp_ppn,
    }