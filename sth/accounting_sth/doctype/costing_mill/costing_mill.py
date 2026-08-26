# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import erpnext
import frappe
from erpnext.accounts.general_ledger import make_gl_entries, make_reverse_gl_entries
from frappe.model.document import Document
from frappe.utils import flt

# Akhiran anak akun stasiun. Akun grup stasiun di Station Procurement Settings
# (mis. 63010) ditambah akhirannya jadi akun anaknya: 6301001 OPERASIONAL,
# 6301004 SERVICE DAN MAINTENANCE.
AKHIRAN_OPERASIONAL = "01"
AKHIRAN_SERVICE = "04"

KETERANGAN_GAJI = "ALOKASI GAJI KARYAWAN MILL"
KETERANGAN_BENGKEL = "ALOKASI GAJI OPERATOR BENGKEL MILL"


class CostingMill(Document):

	def validate(self):
		self.validasi_periode()
		self.hitung_total()

	def on_submit(self):
		self.make_gl_entry()

	def on_cancel(self):
		self.ignore_linked_doctypes = ("GL Entry",)
		self.make_gl_entry()

	def on_trash(self):
		frappe.db.delete("GL Entry", {
			"voucher_type": self.doctype,
			"voucher_no": self.name,
		})

	def validasi_periode(self):
		if self.periode_dari and self.periode_sampai and self.periode_dari > self.periode_sampai:
			frappe.throw("Periode Dari tidak boleh melewati Periode Sampai.")

	def make_gl_entry(self):
		if self.docstatus == 1:
			make_gl_entries(self.get_gl_entries(), merge_entries=False)
		elif self.docstatus == 2:
			make_reverse_gl_entries(voucher_type=self.doctype, voucher_no=self.name)

	def get_gl_entries(self):
		"""Jurnal diambil dari tabel Closing saja.

		Pengeluaran Barang sengaja tidak ikut: Stock Entry-nya sudah menjurnal
		sendiri ke akun dan cost center stasiun waktu Pengeluaran Barang disubmit.
		"""
		gl_entries = []
		default_cost_center = erpnext.get_default_cost_center(self.company)

		total_debit = 0
		total_credit = 0

		for row in self.costing_mill_closing:
			cost_center = row.cost_center or default_cost_center

			if row.debit:
				total_debit += flt(row.debit)
				gl_entries.append(self.get_gl_dict({
					"account": row.no_coa,
					"cost_center": cost_center,
					"debit": row.debit,
					"debit_in_account_currency": row.debit,
					"remarks": row.keterangan,
				}))
			if row.credit:
				total_credit += flt(row.credit)
				gl_entries.append(self.get_gl_dict({
					"account": row.no_coa,
					"cost_center": cost_center,
					"credit": row.credit,
					"credit_in_account_currency": row.credit,
					"remarks": row.keterangan,
				}))

		if gl_entries and flt(total_debit, 2) != flt(total_credit, 2):
			frappe.throw(
				"Debit ({0}) dan Kredit ({1}) di tabel Closing tidak seimbang. "
				"Jalankan ulang Ambil Data.".format(flt(total_debit, 2), flt(total_credit, 2))
			)

		return gl_entries

	def get_gl_dict(self, args):
		gl_dict = frappe._dict({
			"company": self.company,
			"posting_date": self.periode_sampai,
			"voucher_type": self.doctype,
			"voucher_no": self.name,
			"remarks": "Costing Mill {0}".format(self.name),
			"against": None,
			"debit": 0,
			"credit": 0,
			"debit_in_account_currency": 0,
			"credit_in_account_currency": 0,
			"is_opening": "No",
			"party_type": None,
			"party": None,
			"cost_center": None,
			"company_currency": erpnext.get_company_currency(self.company),
		})
		gl_dict.update(args)
		return gl_dict

	def hitung_total(self):
		self.total_gaji_karyawan = sum(flt(d.amount) for d in self.costing_mill_gaji_karyawan)
		self.total_gaji_operator_bengkel = sum(flt(d.amount) for d in self.costing_mill_gaji_operator_bengkel)
		self.total_pengeluaran_barang = sum(flt(d.amount) for d in self.costing_mill_pengeluaran_barang)
		self.total_hm = sum(flt(d.total_hm) for d in self.costing_mill_hm_stasiun)
		self.total_alokasi_bengkel = sum(flt(d.amount) for d in self.costing_mill_hm_stasiun)
		self.total_closing = sum(flt(d.debit) for d in self.costing_mill_closing)
		self.grand_total = (
			flt(self.total_gaji_karyawan)
			+ flt(self.total_gaji_operator_bengkel)
			+ flt(self.total_pengeluaran_barang)
		)


# ---------------------------------------------------------------------------
# Pencarian COA dan Cost Center
# ---------------------------------------------------------------------------

def get_coa_anak_stasiun(stasiun, company, akhiran):
	"""Anak akun sebuah stasiun menurut akhiran nomornya.

	Akun grup stasiun disimpan di Station Procurement Settings per company
	(mis. 63010 - PENGOLAHAN PABRIK - STASIUN RECEPTION). Anaknya bernomor grup
	+ akhiran, mis. 6301001 - STASIUN RECEPTION - OPERASIONAL.
	"""
	akun_grup = frappe.db.get_value("Station Procurement Settings", {
		"parent": stasiun,
		"parenttype": "Station Master",
		"company": company,
	}, "account")

	if not akun_grup:
		return None

	nomor_grup = frappe.db.get_value("Account", akun_grup, "account_number")
	if not nomor_grup:
		return None

	return frappe.db.get_value("Account", {
		"company": company,
		"account_number": nomor_grup + akhiran,
		"is_group": 0,
	}, "name")


@frappe.whitelist()
def get_coa_operasional_stasiun(stasiun, company):
	"""Akun OPERASIONAL milik sebuah stasiun, tempat gaji karyawan stasiun itu."""
	return get_coa_anak_stasiun(stasiun, company, AKHIRAN_OPERASIONAL)


@frappe.whitelist()
def get_coa_service_stasiun(stasiun, company):
	"""Akun SERVICE DAN MAINTENANCE milik sebuah stasiun.

	Ke sinilah biaya bengkel mill dibebankan: pekerjaan bengkel di sebuah
	stasiun adalah perawatan stasiun itu, bukan biaya operasionalnya.
	"""
	return get_coa_anak_stasiun(stasiun, company, AKHIRAN_SERVICE)


@frappe.whitelist()
def get_coa_gaji_dialokasi(company):
	"""Akun kredit alokasi gaji, diambil dari STH Accounting Settings.

	Barisnya dicocokkan per company di tabel STH Accounting Settings Payroll,
	akun yang sama yang dipakai Payroll Entry waktu mendebit beban gaji, jadi
	jurnal alokasi ini murni reclass beban ke stasiun.
	"""
	settings = frappe.get_single("STH Accounting Settings")
	for row in settings.sth_accounting_settings_payroll:
		if row.company == company:
			return row.account
	return None


def get_cost_center_stasiun(stasiun, company, unit=None):
	"""Cost Center sebuah stasiun.

	Yang dipakai duluan adalah cost_center di Detail Station Master karena itu
	setelan eksplisit per unit. Kalau kosong, dipakai pola yang sama dengan
	Pengeluaran Barang ("<nama stasiun> - <abbr>") supaya biaya mill tidak
	terpecah ke dua cost center yang berbeda.
	"""
	filters = {"parent": stasiun, "parenttype": "Station Master"}
	if unit:
		filters["unit"] = unit

	cost_center = frappe.db.get_value("Detail Station Master", filters, "cost_center")
	if cost_center:
		return cost_center

	nama_stasiun = frappe.db.get_value("Station Master", stasiun, "machine_name")
	if not nama_stasiun:
		return None

	abbr = frappe.db.get_value("Company", company, "abbr")
	kandidat = "{0} - {1}".format(nama_stasiun, abbr)

	return kandidat if frappe.db.exists("Cost Center", kandidat) else None


# ---------------------------------------------------------------------------
# Sumber biaya
# ---------------------------------------------------------------------------

def kondisi_mekanik_bkm(company=None, unit=None, negasi=False):
	"""Klausa EXISTS: karyawan yang punya Buku Kerja Mekanik di periode ini.

	Inilah pemisah antara gaji karyawan mill dan gaji operator bengkel. Yang
	tercatat mengerjakan sesuatu di Buku Kerja Mekanik masuk pool bengkel yang
	dibagi menurut HM; sisanya dibebankan langsung ke stasiunnya masing-masing.

	Dulu pemisahnya nama jabatan yang mengandung "BENGKEL". Jabatan tidak
	menentukan siapa yang benar-benar bekerja di bengkel pada periode tertentu,
	dan sumbernya juga beda dari yang dipakai get_hm_stasiun() sebagai pembagi —
	sekarang keduanya bersandar pada Buku Kerja Mekanik yang sama.
	"""
	return """
		{negasi} EXISTS (
			SELECT 1
			FROM `tabBuku Kerja Mekanik` bkm
			WHERE bkm.docstatus = 1
			  AND bkm.nama_karyawan = ss.employee
			  AND bkm.tanggal BETWEEN %(dari)s AND %(sampai)s
			  {company}
			  {unit}
		)
	""".format(
		negasi="NOT" if negasi else "",
		company="AND bkm.company = %(company)s" if company else "",
		unit="AND bkm.unit = %(unit)s" if unit else "",
	)


@frappe.whitelist()
def get_gaji_karyawan_mill(periode_dari, periode_sampai, company=None, unit=None):
	"""Gaji karyawan mill yang stasiunnya sudah jelas, langsung ke stasiun itu.

	Karyawan yang punya Buku Kerja Mekanik di periode ini dikecualikan — biayanya
	masuk pool yang dibagi berdasarkan HM lewat get_gaji_operator_bengkel_mill().

	Nilainya memakai net_pay supaya persis sama dengan yang sudah dibebankan
	waktu accrual Payroll Entry; kalau dipakai gross_pay, kredit alokasi akan
	lebih besar dari beban yang pernah dijurnal sebesar total potongan.
	"""
	unit_filter = "AND e.unit = %(unit)s" if unit else ""
	company_filter = "AND ss.company = %(company)s" if company else ""

	rows = frappe.db.sql("""
		SELECT
			ss.name AS salary_slip,
			ss.employee,
			ss.employee_name,
			ss.net_pay AS amount,
			e.stasiun,
			e.coa_stasiun
		FROM `tabSalary Slip` ss
		JOIN `tabEmployee` e ON e.name = ss.employee
		JOIN `tabUnit` u ON u.name = e.unit AND u.mill = 1
		WHERE ss.docstatus = 1
		  AND ss.start_date >= %(dari)s
		  AND ss.end_date <= %(sampai)s
		  AND e.stasiun IS NOT NULL AND e.stasiun != ''
		  AND {kondisi_bkm}
		  {company_filter}
		  {unit_filter}
		ORDER BY e.stasiun, ss.employee_name
	""".format(
		company_filter=company_filter,
		unit_filter=unit_filter,
		kondisi_bkm=kondisi_mekanik_bkm(company, unit, negasi=True),
	), {
		"dari": periode_dari, "sampai": periode_sampai, "company": company, "unit": unit,
	}, as_dict=True)

	result = []
	for r in rows:
		no_coa = r.coa_stasiun or get_coa_operasional_stasiun(r.stasiun, company)
		result.append({
			"salary_slip": r.salary_slip,
			"employee": r.employee,
			"employee_name": r.employee_name,
			"stasiun": r.stasiun,
			"no_coa": no_coa,
			"amount": flt(r.amount),
			"keterangan": KETERANGAN_GAJI,
		})

	return result


@frappe.whitelist()
def get_gaji_operator_bengkel_mill(periode_dari, periode_sampai, company=None, unit=None):
	"""Gaji operator bengkel mill — pool yang dibagi ke stasiun menurut HM.

	Isinya karyawan yang tercatat mengerjakan sesuatu di Buku Kerja Mekanik
	sepanjang periode ini, yaitu sumber yang sama dengan HM pembaginya di
	get_hm_stasiun(). Bengkel tidak punya stasiun sendiri di COA, jadi biayanya
	tidak bisa dibebankan langsung.

	Stasiun karyawannya tetap ikut dibawa — bukan untuk membebani stasiun itu,
	tapi untuk tahu cost center mana yang harus dikredit balik waktu closing.
	"""
	unit_filter = "AND e.unit = %(unit)s" if unit else ""
	company_filter = "AND ss.company = %(company)s" if company else ""

	rows = frappe.db.sql("""
		SELECT
			ss.name AS salary_slip,
			ss.employee,
			ss.employee_name,
			ss.net_pay AS amount,
			e.designation,
			e.stasiun,
			e.unit
		FROM `tabSalary Slip` ss
		JOIN `tabEmployee` e ON e.name = ss.employee
		JOIN `tabUnit` u ON u.name = e.unit AND u.mill = 1
		WHERE ss.docstatus = 1
		  AND ss.start_date >= %(dari)s
		  AND ss.end_date <= %(sampai)s
		  AND {kondisi_bkm}
		  {company_filter}
		  {unit_filter}
		ORDER BY ss.employee_name
	""".format(
		company_filter=company_filter,
		unit_filter=unit_filter,
		kondisi_bkm=kondisi_mekanik_bkm(company, unit),
	), {
		"dari": periode_dari, "sampai": periode_sampai, "company": company, "unit": unit,
	}, as_dict=True)

	return [{
		"salary_slip": r.salary_slip,
		"employee": r.employee,
		"employee_name": r.employee_name,
		"designation": r.designation,
		"stasiun": r.stasiun,
		"unit": r.unit,
		"amount": flt(r.amount),
		"keterangan": KETERANGAN_BENGKEL,
	} for r in rows]


@frappe.whitelist()
def get_pengeluaran_barang_mill(periode_dari, periode_sampai, company=None, unit=None):
	"""Pengeluaran barang yang dibebankan ke stasiun mill.

	Nilainya diambil dari Stock Ledger Entry milik Stock Entry-nya, bukan dari
	harga di dokumen permintaan, supaya sama persis dengan yang sudah masuk GL.
	"""
	company_filter = "AND pb.pt_pemilik_barang = %(company)s" if company else ""
	unit_filter = "AND pb.unit = %(unit)s" if unit else ""

	pb_items = frappe.db.sql("""
		SELECT
			pb.name AS no_pb,
			ste.name AS ste_reference,
			pbi.kode_barang,
			pbi.item_name,
			pbi.stasiun,
			pbi.account
		FROM `tabPengeluaran Barang` pb
		JOIN `tabPengeluaran Barang Item` pbi ON pbi.parent = pb.name
		JOIN `tabStock Entry` ste ON ste.pengeluaran_barang = pb.name AND ste.docstatus = 1
		WHERE pb.docstatus = 1
		  AND pb.tanggal BETWEEN %(dari)s AND %(sampai)s
		  AND pbi.stasiun IS NOT NULL
		  AND pbi.stasiun != ''
		  {company_filter}
		  {unit_filter}
		ORDER BY pb.tanggal, pb.name, pbi.stasiun
	""".format(company_filter=company_filter, unit_filter=unit_filter), {
		"dari": periode_dari, "sampai": periode_sampai, "company": company, "unit": unit,
	}, as_dict=True)

	result = []
	for item in pb_items:
		amount = 0.0

		if item.ste_reference:
			sle = frappe.db.sql("""
				SELECT ABS(SUM(stock_value_difference)) AS total
				FROM `tabStock Ledger Entry`
				WHERE voucher_type = 'Stock Entry'
				  AND voucher_no = %(ste)s
				  AND item_code = %(item_code)s
				  AND stock_value_difference < 0
			""", {"ste": item.ste_reference, "item_code": item.kode_barang}, as_dict=True)

			if sle and sle[0].total:
				amount = flt(sle[0].total)

		result.append({
			"pengeluaran_barang": item.no_pb,
			"stasiun": item.stasiun,
			"no_coa": item.account,
			"amount": amount,
			"keterangan": item.item_name or item.kode_barang,
		})

	return result


# ---------------------------------------------------------------------------
# Aktivitas (HM) dan alokasi
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_hm_stasiun(periode_dari, periode_sampai, company=None, unit=None):
	"""Jam kerja per stasiun dari Buku Kerja Mekanik.

	Jamnya dihitung per dokumen, tidak dikali jumlah mekanik yang ikut
	mengerjakan — satu pekerjaan 3 jam oleh 4 orang tetap dihitung 3 HM.

	Preventive Maintenance dulu ikut menyumbang HM di sini dan sekarang tidak
	lagi: alokasi bengkel bersandar sepenuhnya pada Buku Kerja Mekanik.
	"""
	params = {"dari": periode_dari, "sampai": periode_sampai, "company": company, "unit": unit}

	rows = frappe.db.sql("""
		SELECT kode_stasiun AS stasiun, SUM(total_jam_desimal) AS total_jam
		FROM `tabBuku Kerja Mekanik`
		WHERE docstatus = 1
		  AND tanggal BETWEEN %(dari)s AND %(sampai)s
		  AND kode_stasiun IS NOT NULL AND kode_stasiun != ''
		  {company_filter}
		  {unit_filter}
		GROUP BY kode_stasiun
	""".format(
		company_filter="AND company = %(company)s" if company else "",
		unit_filter="AND unit = %(unit)s" if unit else "",
	), params, as_dict=True)

	nama_stasiun = {
		r.stasiun: frappe.db.get_value("Station Master", r.stasiun, "machine_name") for r in rows
	}

	result = [
		{
			"stasiun": r.stasiun,
			"nama_stasiun": nama_stasiun.get(r.stasiun),
			"total_hm": flt(r.total_jam, 2),
		}
		for r in rows
	]

	result.sort(key=lambda r: -r["total_hm"])
	return result


def get_hm_karyawan_stasiun(periode_dari, periode_sampai, company=None, unit=None):
	"""HM tiap karyawan di tiap stasiun, dari Buku Kerja Mekanik.

	Satu Buku Kerja Mekanik berisi satu karyawan, jadi jamnya bisa dipilah per
	orang tanpa perlu tabel bantu. Hasilnya {karyawan: {stasiun: jam}}.
	"""
	params = {"dari": periode_dari, "sampai": periode_sampai, "company": company, "unit": unit}

	rows = frappe.db.sql("""
		SELECT
			nama_karyawan AS employee,
			kode_stasiun AS stasiun,
			SUM(total_jam_desimal) AS total_jam
		FROM `tabBuku Kerja Mekanik`
		WHERE docstatus = 1
		  AND tanggal BETWEEN %(dari)s AND %(sampai)s
		  AND kode_stasiun IS NOT NULL AND kode_stasiun != ''
		  AND nama_karyawan IS NOT NULL AND nama_karyawan != ''
		  {company_filter}
		  {unit_filter}
		GROUP BY nama_karyawan, kode_stasiun
	""".format(
		company_filter="AND company = %(company)s" if company else "",
		unit_filter="AND unit = %(unit)s" if unit else "",
	), params, as_dict=True)

	hasil = {}
	for r in rows:
		if flt(r.total_jam) <= 0:
			continue
		hasil.setdefault(r.employee, {})[r.stasiun] = flt(r.total_jam)

	return hasil


def hitung_alokasi_hm(hm_rows, pool_rows, hm_karyawan, company):
	"""Bagi gaji tiap operator ke stasiun yang dia kerjakan sendiri.

	Pembaginya HM karyawan itu sendiri di tiap stasiun, bukan HM seluruh stasiun.
	Gaji operator yang sebulan penuh memegang satu stasiun tidak boleh ikut
	membebani stasiun lain yang kebetulan punya HM; itu yang terjadi kalau
	seluruh pool dibagi rata menurut HM gabungan.

	Karyawan yang gajinya masuk pool tapi tidak punya HM berstasiun sama sekali
	dibagi menurut HM seluruh stasiun. Nilainya tetap harus keluar, kalau tidak
	kredit alokasi di closing tidak seimbang dengan debitnya.

	Akunnya SERVICE DAN MAINTENANCE stasiun yang dicatat di transaksi bengkel,
	bukan OPERASIONAL: yang dibebankan di sini kerja bengkel di stasiun itu.

	Sisa pembulatan dibebankan ke stasiun beralokasi terbesar supaya jumlahnya
	persis sama dengan pool dan jurnalnya seimbang.
	"""
	baris = [dict(r) for r in hm_rows]
	total_hm = sum(flt(r["total_hm"]) for r in baris)
	total_pool = sum(flt(r.get("amount")) for r in pool_rows)

	for r in baris:
		r["porsi"] = 0
		r["amount"] = 0
		r["no_coa"] = get_coa_service_stasiun(r["stasiun"], company)

	if not baris or not total_hm or not total_pool:
		return baris

	baris.sort(key=lambda r: -flt(r["total_hm"]))
	per_stasiun = {r["stasiun"]: 0.0 for r in baris}

	for orang in pool_rows:
		gaji = flt(orang.get("amount"))
		if not gaji:
			continue

		jam = {
			stasiun: flt(nilai)
			for stasiun, nilai in (hm_karyawan.get(orang.get("employee")) or {}).items()
			if stasiun in per_stasiun
		}
		pembagi = sum(jam.values())

		if not pembagi:
			jam = {r["stasiun"]: flt(r["total_hm"]) for r in baris}
			pembagi = total_hm

		for stasiun, nilai in jam.items():
			per_stasiun[stasiun] += gaji * nilai / pembagi

	terbagi = 0
	for r in baris:
		amount = flt(per_stasiun[r["stasiun"]], 2)
		r["amount"] = amount
		# Porsi sekarang porsi rupiah, bukan porsi HM: keduanya tidak lagi sama
		# begitu gaji dibagi per karyawan.
		r["porsi"] = flt(amount / total_pool * 100, 4)
		terbagi += amount

	selisih = flt(flt(total_pool) - terbagi, 2)
	if selisih:
		penerima = max(baris, key=lambda r: flt(r["amount"]))
		penerima["amount"] = flt(penerima["amount"] + selisih, 2)
		penerima["porsi"] = flt(penerima["amount"] / total_pool * 100, 4)

	return baris


@frappe.whitelist()
def get_alokasi_hm_stasiun(periode_dari, periode_sampai, company=None, unit=None):
	"""Baris HM per stasiun lengkap dengan porsi dan nilai alokasinya."""
	hm_rows = get_hm_stasiun(periode_dari, periode_sampai, company, unit)
	pool_rows = get_gaji_operator_bengkel_mill(periode_dari, periode_sampai, company, unit)
	hm_karyawan = get_hm_karyawan_stasiun(periode_dari, periode_sampai, company, unit)

	return hitung_alokasi_hm(hm_rows, pool_rows, hm_karyawan, company)


def baris_kredit_alokasi(coa_kredit, kredit_per_cost_center, total_debit):
	"""Baris kredit gaji dialokasi, satu baris per cost center asal.

	Sisa pembulatan dibebankan ke baris terbesar supaya total kredit persis sama
	dengan total debit; kalau tidak, submit-nya ditolak oleh cek keseimbangan di
	get_gl_entries().
	"""
	baris = [
		{
			"no_coa": coa_kredit,
			"stasiun": None,
			"cost_center": cost_center,
			"debit": 0,
			"credit": flt(amount, 2),
			"keterangan": "ALOKASI BIAYA GAJI MILL KE STASIUN",
		}
		for cost_center, amount in sorted(
			kredit_per_cost_center.items(), key=lambda d: -flt(d[1])
		)
		if flt(amount, 2)
	]

	if not baris:
		return baris

	selisih = flt(flt(total_debit, 2) - sum(flt(b["credit"]) for b in baris), 2)
	if selisih:
		baris[0]["credit"] = flt(baris[0]["credit"] + selisih, 2)

	return baris


@frappe.whitelist()
def get_closing_mill(periode_dari, periode_sampai, company=None, unit=None):
	"""Baris jurnal akhir: debit per stasiun, kredit ke akun gaji dialokasi.

	Dua sumber yang dijurnal di sini adalah gaji karyawan mill (langsung ke
	stasiun karyawannya) dan gaji operator bengkel (dibagi menurut HM).

	Kreditnya dipecah per cost center asal, yaitu cost center stasiun yang
	dipakai waktu accrual Payroll Entry. Kalau kreditnya ditumpuk di satu cost
	center, stasiun akan kelihatan dobel beban dan cost center default jadi
	minus, padahal totalnya nol.
	"""
	coa_kredit = get_coa_gaji_dialokasi(company)
	if not coa_kredit:
		frappe.throw(
			"Akun alokasi gaji untuk company {0} belum diisi di STH Accounting Settings "
			"tabel Payroll.".format(company)
		)

	# Gaji karyawan mill dijumlahkan per stasiun supaya jurnalnya ringkas,
	# rinciannya tetap kelihatan di tabel Gaji Karyawan Mill.
	per_stasiun = {}
	for r in get_gaji_karyawan_mill(periode_dari, periode_sampai, company, unit):
		kunci = (r["stasiun"], r["no_coa"])
		per_stasiun[kunci] = per_stasiun.get(kunci, 0) + flt(r["amount"])

	rows = []
	total = 0
	kredit_per_cost_center = {}

	for (stasiun, no_coa), amount in per_stasiun.items():
		if not amount:
			continue
		cost_center = get_cost_center_stasiun(stasiun, company, unit)
		total += flt(amount)
		kredit_per_cost_center[cost_center] = (
			kredit_per_cost_center.get(cost_center, 0) + flt(amount)
		)
		rows.append({
			"no_coa": no_coa,
			"stasiun": stasiun,
			"cost_center": cost_center,
			"debit": flt(amount, 2),
			"credit": 0,
			"keterangan": KETERANGAN_GAJI,
		})

	total_alokasi_bengkel = 0
	for r in get_alokasi_hm_stasiun(periode_dari, periode_sampai, company, unit):
		if not r.get("amount"):
			continue
		total += flt(r["amount"])
		total_alokasi_bengkel += flt(r["amount"])
		rows.append({
			"no_coa": r["no_coa"],
			"stasiun": r["stasiun"],
			"cost_center": get_cost_center_stasiun(r["stasiun"], company, unit),
			"debit": flt(r["amount"], 2),
			"credit": 0,
			"keterangan": KETERANGAN_BENGKEL,
		})

	# Kredit balik gaji bengkel ke cost center karyawan bengkelnya sendiri,
	# bukan ke stasiun yang menerima alokasi HM. Yang dikredit cuma sebesar yang
	# benar-benar teralokasi: kalau HM-nya belum ada, alokasinya nol dan jurnal
	# ini harus ikut nol supaya tetap seimbang.
	bengkel_per_cost_center = {}
	pool_bengkel = 0

	for r in get_gaji_operator_bengkel_mill(periode_dari, periode_sampai, company, unit):
		if not flt(r["amount"]):
			continue
		cost_center = get_cost_center_stasiun(r["stasiun"], company, r.get("unit") or unit) \
			if r.get("stasiun") else None
		bengkel_per_cost_center[cost_center] = (
			bengkel_per_cost_center.get(cost_center, 0) + flt(r["amount"])
		)
		pool_bengkel += flt(r["amount"])

	if pool_bengkel and total_alokasi_bengkel:
		for cost_center, amount in bengkel_per_cost_center.items():
			porsi = flt(amount) / pool_bengkel * total_alokasi_bengkel
			kredit_per_cost_center[cost_center] = (
				kredit_per_cost_center.get(cost_center, 0) + porsi
			)
	elif pool_bengkel:
		frappe.msgprint(
			"Gaji operator bengkel {0} tidak dialokasi karena belum ada HM stasiun "
			"pada periode ini.".format(frappe.format(pool_bengkel, {"fieldtype": "Currency"})),
			title="Alokasi Bengkel Kosong",
			indicator="orange",
		)

	if total:
		# Patokannya debit yang sudah dibulatkan per baris, bukan total mentahnya,
		# supaya tidak meleset satu sen dari cek keseimbangan waktu submit.
		total_debit = sum(flt(r["debit"]) for r in rows)
		rows.extend(baris_kredit_alokasi(coa_kredit, kredit_per_cost_center, total_debit))

	return rows


@frappe.whitelist()
def build_and_submit_costing_mill(company, unit, periode_dari, periode_sampai):
	"""Buat dan submit Costing Mill di sisi server.

	Isinya sama persis dengan tombol Ambil Data di form, dipakai kalau costing
	mau dijalankan otomatis saat tutup buku.
	"""
	gaji_rows = get_gaji_karyawan_mill(periode_dari, periode_sampai, company, unit)
	operator_rows = get_gaji_operator_bengkel_mill(periode_dari, periode_sampai, company, unit)
	hm_rows = get_alokasi_hm_stasiun(periode_dari, periode_sampai, company, unit)
	pengeluaran_rows = get_pengeluaran_barang_mill(periode_dari, periode_sampai, company, unit)

	# Unit tanpa mill dilewati sebelum tabel Closing disusun: unit kebun tidak
	# perlu ditinggali Costing Mill kosong tiap bulan, juga tidak perlu ikut
	# ditegur soal akun alokasi gaji yang cuma dipakai jurnal alokasi. Yang
	# datanya ada tapi belum lengkap tetap dibuat supaya kekurangannya kelihatan.
	if not (gaji_rows or operator_rows or hm_rows or pengeluaran_rows):
		return None

	cm = frappe.new_doc("Costing Mill")
	cm.company = company
	cm.unit = unit
	cm.periode_dari = periode_dari
	cm.periode_sampai = periode_sampai

	for row in gaji_rows:
		cm.append("costing_mill_gaji_karyawan", row)

	for row in operator_rows:
		cm.append("costing_mill_gaji_operator_bengkel", row)

	for row in hm_rows:
		cm.append("costing_mill_hm_stasiun", row)

	for row in pengeluaran_rows:
		cm.append("costing_mill_pengeluaran_barang", row)

	for row in get_closing_mill(periode_dari, periode_sampai, company, unit):
		cm.append("costing_mill_closing", row)

	cm.insert(ignore_permissions=True)
	cm.submit()

	return cm.name
