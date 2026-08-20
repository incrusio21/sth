# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

"""Alokasi gaji kebun ke kegiatan panen dan perawatan.

Upah dan premi yang lahir dari BKM sudah dijurnal sendiri waktu BKM disubmit
(debit akun kegiatan, kredit akun kredit BKM), jadi yang dibagi di sini cuma
komponen gaji selain itu: HKnE, lembur, natura, premi yang tidak bersumber dari
BKM, dan BPJS beban perusahaan.

Cara baginya rata per kegiatan: total komponen seorang karyawan dalam sebulan
dibagi banyaknya kegiatan yang dia kerjakan, dihitung per BKM per blok. Penyebut
menggabungkan kegiatan panen dan perawatan supaya gaji satu orang tidak dihitung
dua kali oleh dua costing yang berbeda.
"""

import erpnext
import frappe
from erpnext.accounts.general_ledger import make_gl_entries, make_reverse_gl_entries
from frappe.model.document import Document
from frappe.utils import flt

# Sama dengan yang dipakai Costing Mill: akun kontra beban, bukan hutang gaji.
# Payroll sudah menjurnal beban gaji lawan hutang gaji, jadi alokasi ini murni
# reclass beban ke kegiatan.
NOMOR_COA_GAJI_DIALOKASI = "6211099"

# Komponen yang dibagi ke kegiatan. Upah Panen/Perawatan/Traksi dan premi yang
# lahir dari BKM (brondolan, angkut, supervisi) sengaja tidak ada di sini: kalau
# ikut, akun kegiatan terdebit dua kali. Gaji Pokok juga tidak ikut sesuai
# rentang HKnE s.d. BPJS Kesehatan di form gaji kebun.
KOMPONEN_COSTING_KEBUN = (
	"HKnE",
	"Lembur",
	"Natura",
	"Premi Kehadiran",
	"Premi Tutup Buku",
	"Gaji Pokok"
)

# BPJS beban perusahaan namanya bervariasi (JKK punya beberapa varian RS/RT/RSD),
# jadi disaring dengan pola, bukan daftar tetap. Yang beban karyawan tidak kena
# karena baris yang dibaca cuma parentfield "earnings".
POLA_KOMPONEN_BPJS = (
	"BPJS% (Perusahaan)",
	"BPJS TK - JK%",
)

SUMBER_PANEN = "Panen"
SUMBER_PERAWATAN = "Perawatan"

KETERANGAN = {
	SUMBER_PANEN: "ALOKASI GAJI KE KEGIATAN PANEN",
	SUMBER_PERAWATAN: "ALOKASI GAJI KE KEGIATAN PERAWATAN",
}


class CostingKebun(Document):
	"""Induk Costing Panen dan Costing Perawatan.

	Bedanya cuma di kegiatan mana yang dijurnal; pembagian gajinya persis sama
	dan dihitung dari gabungan kedua sumber.
	"""

	sumber = None

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

	@frappe.whitelist()
	def ambil_data(self):
		"""Isi ulang ketiga tabel dari BKM dan slip gaji periode ini."""
		if not (self.periode_dari and self.periode_sampai):
			frappe.throw("Harap isi Periode Dari dan Periode Sampai terlebih dahulu.")

		if not self.company:
			frappe.throw("Harap isi Company terlebih dahulu.")

		self.isi_data(get_data_costing_kebun(
			self.sumber, self.periode_dari, self.periode_sampai, self.company, self.unit
		))

	def isi_data(self, data):
		"""Tulis hasil pembagian ke ketiga tabel, menimpa isi sebelumnya."""
		for fieldname, rows in (
			("costing_kebun_gaji_karyawan", data["gaji_karyawan"]),
			("costing_kebun_kegiatan", data["kegiatan"]),
			("costing_kebun_closing", data["closing"]),
		):
			self.set(fieldname, [])
			for row in rows:
				self.append(fieldname, row)

		self.hitung_total()

	def hitung_total(self):
		self.total_gaji_karyawan = sum(flt(d.amount) for d in self.costing_kebun_gaji_karyawan)
		self.total_kegiatan = sum(flt(d.amount) for d in self.costing_kebun_kegiatan)
		self.total_closing = sum(flt(d.debit) for d in self.costing_kebun_closing)

	def make_gl_entry(self):
		if self.docstatus == 1:
			make_gl_entries(self.get_gl_entries(), merge_entries=False)
		elif self.docstatus == 2:
			make_reverse_gl_entries(voucher_type=self.doctype, voucher_no=self.name)

	def get_gl_entries(self):
		"""Jurnal diambil dari tabel Closing saja.

		Tabel Kegiatan cuma rincian per karyawan per BKM; yang diposting adalah
		rekapnya per akun kegiatan supaya jumlah GL Entry tidak meledak.
		"""
		gl_entries = []
		default_cost_center = erpnext.get_default_cost_center(self.company)

		total_debit = 0
		total_credit = 0

		for row in self.costing_kebun_closing:
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
			"remarks": "{0} {1}".format(self.doctype, self.name),
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


# ---------------------------------------------------------------------------
# Sumber data
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_coa_gaji_dialokasi(company):
	"""Akun kontra 6211099 - BIAYA GAJI DAN UPAH DIALOKASI."""
	return frappe.db.get_value("Account", {
		"company": company,
		"account_number": NOMOR_COA_GAJI_DIALOKASI,
		"is_group": 0,
	}, "name")


def get_komponen_gaji(periode_dari, periode_sampai, company=None, unit=None):
	"""Total komponen gaji yang dibagi ke kegiatan, per karyawan.

	Cost center accrual ikut dibawa: itu cost center Payroll Entry yang mendebit
	beban gaji, dan ke situ pula kreditnya harus dikembalikan waktu closing.
	"""
	pola = " OR ".join(
		["sd.salary_component LIKE %(pola_{0})s".format(i) for i in range(len(POLA_KOMPONEN_BPJS))]
	)

	params = {
		"dari": periode_dari,
		"sampai": periode_sampai,
		"company": company,
		"unit": unit,
		"komponen": KOMPONEN_COSTING_KEBUN,
	}
	for i, p in enumerate(POLA_KOMPONEN_BPJS):
		params["pola_{0}".format(i)] = p

	rows = frappe.db.sql("""
		SELECT
			ss.employee,
			ss.employee_name,
			pe.cost_center AS cost_center_accrual,
			SUM(sd.amount) AS amount
		FROM `tabSalary Slip` ss
		JOIN `tabSalary Detail` sd
			ON sd.parent = ss.name AND sd.parentfield = 'earnings'
		JOIN `tabEmployee` e ON e.name = ss.employee
		LEFT JOIN `tabPayroll Entry` pe ON pe.name = ss.payroll_entry
		WHERE ss.docstatus = 1
		  AND ss.start_date >= %(dari)s
		  AND ss.end_date <= %(sampai)s
		  AND (sd.salary_component IN %(komponen)s OR {pola})
		  {company_filter}
		  {unit_filter}
		GROUP BY ss.employee, ss.employee_name, pe.cost_center
	""".format(
		pola=pola,
		company_filter="AND ss.company = %(company)s" if company else "",
		unit_filter="AND e.unit = %(unit)s" if unit else "",
	), params, as_dict=True)

	komponen = {}
	for r in rows:
		data = komponen.setdefault(r.employee, {
			"employee_name": r.employee_name,
			"cost_center_accrual": r.cost_center_accrual,
			"amount": 0,
		})
		data["amount"] += flt(r.amount)
		# Slip yang tidak lewat Payroll Entry tidak punya cost center accrual;
		# yang ada dipakai supaya kreditnya tetap ketemu asalnya.
		if not data["cost_center_accrual"]:
			data["cost_center_accrual"] = r.cost_center_accrual

	return komponen


def get_kegiatan_karyawan(periode_dari, periode_sampai, company=None, unit=None):
	"""Kegiatan yang dikerjakan tiap karyawan, satu baris per BKM per blok.

	Karyawan yang tercatat tidak masuk (Absent) tidak dihitung sebagai kegiatan
	— dia tidak mengerjakan apa pun di BKM itu.
	"""
	params = {"dari": periode_dari, "sampai": periode_sampai, "company": company, "unit": unit}
	company_filter = "AND bkm.company = %(company)s" if company else ""
	unit_filter = "AND bkm.unit = %(unit)s" if unit else ""

	panen = frappe.db.sql("""
		SELECT
			bkm.name AS bkm,
			bkm.posting_date AS tanggal,
			bkm.kegiatan,
			bkm.kegiatan_account,
			bkm.cost_center,
			d.employee,
			d.blok
		FROM `tabBuku Kerja Mandor Panen` bkm
		JOIN `tabDetail BKM Hasil Kerja Panen` d ON d.parent = bkm.name
		WHERE bkm.docstatus = 1
		  AND bkm.posting_date BETWEEN %(dari)s AND %(sampai)s
		  AND IFNULL(d.attendance_status, '') != 'Absent'
		  {company_filter}
		  {unit_filter}
		GROUP BY bkm.name, d.employee, d.blok
	""".format(company_filter=company_filter, unit_filter=unit_filter), params, as_dict=True)

	perawatan = frappe.db.sql("""
		SELECT
			bkm.name AS bkm,
			bkm.posting_date AS tanggal,
			bkm.kegiatan,
			bkm.kegiatan_account,
			bkm.cost_center,
			d.employee,
			bkm.blok
		FROM `tabBuku Kerja Mandor Perawatan` bkm
		JOIN `tabDetail BKM Hasil Kerja Perawatan` d ON d.parent = bkm.name
		WHERE bkm.docstatus = 1
		  AND bkm.posting_date BETWEEN %(dari)s AND %(sampai)s
		  AND IFNULL(d.attendance_status, '') != 'Absent'
		  {company_filter}
		  {unit_filter}
		GROUP BY bkm.name, d.employee, bkm.blok
	""".format(company_filter=company_filter, unit_filter=unit_filter), params, as_dict=True)

	rows = []
	for sumber, hasil in ((SUMBER_PANEN, panen), (SUMBER_PERAWATAN, perawatan)):
		for r in hasil:
			r = dict(r)
			r["sumber"] = sumber
			r["bkm_doctype"] = "Buku Kerja Mandor {0}".format(sumber)
			rows.append(r)

	# Urutan tetap supaya sisa pembulatan selalu jatuh ke baris yang sama,
	# berapa kali pun Ambil Data dijalankan.
	rows.sort(key=lambda r: (str(r["tanggal"]), r["sumber"], r["bkm"], r["blok"] or ""))
	return rows


def get_cost_center_blok(blok, company, bawaan=None):
	"""Cost center sebuah blok, pola sama dengan yang dipakai BKM sendiri."""
	if not blok:
		return bawaan

	deskripsi = frappe.db.get_value("Blok", blok, "deskripsi")
	if not deskripsi:
		return bawaan

	abbr = frappe.db.get_value("Company", company, "abbr")
	kandidat = "{0} - {1}".format(deskripsi, abbr)

	return kandidat if frappe.db.exists("Cost Center", kandidat) else bawaan


# ---------------------------------------------------------------------------
# Pembagian
# ---------------------------------------------------------------------------

def bagi_gaji_ke_kegiatan(periode_dari, periode_sampai, company=None, unit=None):
	"""Bagi rata komponen gaji tiap karyawan ke kegiatan yang dia kerjakan.

	Penyebutnya gabungan panen + perawatan. Sisa pembulatan ditaruh di baris
	pertama karyawan yang bersangkutan supaya jumlah alokasinya persis sama
	dengan total komponennya.
	"""
	komponen = get_komponen_gaji(periode_dari, periode_sampai, company, unit)
	kegiatan = get_kegiatan_karyawan(periode_dari, periode_sampai, company, unit)

	per_karyawan = {}
	for r in kegiatan:
		per_karyawan.setdefault(r["employee"], []).append(r)

	hasil = []
	for employee, baris in per_karyawan.items():
		data = komponen.get(employee)
		if not data or not flt(data["amount"]):
			continue

		total = flt(data["amount"])
		jumlah = len(baris)
		porsi = flt(total / jumlah, 2)
		terbagi = 0

		for r in baris:
			r = dict(r)
			r["employee_name"] = data["employee_name"]
			r["cost_center_accrual"] = data["cost_center_accrual"]
			r["total_komponen"] = total
			r["jumlah_kegiatan"] = jumlah
			r["amount"] = porsi
			terbagi += porsi
			hasil.append(r)

		selisih = flt(total - terbagi, 2)
		if selisih:
			hasil[-jumlah]["amount"] = flt(hasil[-jumlah]["amount"] + selisih, 2)

	return hasil


def baris_sumber(semua, sumber):
	return [r for r in semua if r["sumber"] == sumber]


@frappe.whitelist()
def get_alokasi_kegiatan(sumber, periode_dari, periode_sampai, company=None, unit=None):
	"""Baris kegiatan milik satu sumber saja, lengkap dengan nilai alokasinya."""
	semua = bagi_gaji_ke_kegiatan(periode_dari, periode_sampai, company, unit)
	return susun_alokasi_kegiatan(baris_sumber(semua, sumber), company)


def susun_alokasi_kegiatan(baris, company):
	hasil = []
	for r in baris:
		hasil.append({
			"bkm_doctype": r["bkm_doctype"],
			"bkm": r["bkm"],
			"tanggal": r["tanggal"],
			"kegiatan": r["kegiatan"],
			"blok": r["blok"],
			"employee": r["employee"],
			"employee_name": r["employee_name"],
			"no_coa": r["kegiatan_account"],
			"cost_center": get_cost_center_blok(r["blok"], company, r["cost_center"]),
			"amount": flt(r["amount"], 2),
		})

	return hasil


@frappe.whitelist()
def get_gaji_karyawan(sumber, periode_dari, periode_sampai, company=None, unit=None):
	"""Rekap per karyawan: total komponen, jumlah kegiatan, dan porsinya di sini."""
	return susun_gaji_karyawan(
		bagi_gaji_ke_kegiatan(periode_dari, periode_sampai, company, unit), sumber
	)


def susun_gaji_karyawan(baris, sumber):
	rekap = {}
	for r in baris:
		data = rekap.setdefault(r["employee"], {
			"employee": r["employee"],
			"employee_name": r["employee_name"],
			"total_komponen": flt(r["total_komponen"], 2),
			"jumlah_kegiatan": r["jumlah_kegiatan"],
			"jumlah_kegiatan_sumber": 0,
			"amount": 0,
		})

		if r["sumber"] == sumber:
			data["jumlah_kegiatan_sumber"] += 1
			data["amount"] = flt(data["amount"] + flt(r["amount"]), 2)

	return [d for d in rekap.values() if d["jumlah_kegiatan_sumber"]]


@frappe.whitelist()
def get_closing_kebun(sumber, periode_dari, periode_sampai, company=None, unit=None):
	"""Baris jurnal: debit rekap per akun kegiatan, kredit gaji dialokasi.

	Kreditnya dipecah per cost center Payroll Entry yang mendebit beban gajinya,
	supaya kegiatan tidak kelihatan dobel beban dan cost center asal tidak minus.
	"""
	semua = bagi_gaji_ke_kegiatan(periode_dari, periode_sampai, company, unit)
	return susun_closing_kebun(baris_sumber(semua, sumber), sumber, company)


def susun_closing_kebun(baris, sumber, company):
	coa_kredit = get_coa_gaji_dialokasi(company)
	if not coa_kredit:
		frappe.throw(
			"Akun {0} - BIAYA GAJI DAN UPAH DIALOKASI belum ada di company {1}.".format(
				NOMOR_COA_GAJI_DIALOKASI, company
			)
		)

	debit_per_akun = {}
	kredit_per_cost_center = {}

	for r in baris:
		if not flt(r["amount"]):
			continue

		cost_center = get_cost_center_blok(r["blok"], company, r["cost_center"])
		kunci = (r["kegiatan_account"], r["kegiatan"], cost_center)
		debit_per_akun[kunci] = debit_per_akun.get(kunci, 0) + flt(r["amount"])

		asal = r["cost_center_accrual"]
		kredit_per_cost_center[asal] = kredit_per_cost_center.get(asal, 0) + flt(r["amount"])

	rows = []
	for (no_coa, kegiatan, cost_center), amount in sorted(
		debit_per_akun.items(), key=lambda d: (str(d[0][0]), str(d[0][1]), str(d[0][2]))
	):
		if not flt(amount, 2):
			continue
		rows.append({
			"no_coa": no_coa,
			"kegiatan": kegiatan,
			"cost_center": cost_center,
			"debit": flt(amount, 2),
			"credit": 0,
			"keterangan": KETERANGAN[sumber],
		})

	if not rows:
		return rows

	total_debit = sum(flt(r["debit"]) for r in rows)
	rows.extend(baris_kredit_alokasi(coa_kredit, kredit_per_cost_center, total_debit, sumber))

	return rows


def baris_kredit_alokasi(coa_kredit, kredit_per_cost_center, total_debit, sumber):
	"""Baris kredit gaji dialokasi, satu per cost center asal.

	Sisa pembulatan dibebankan ke baris terbesar supaya total kredit persis sama
	dengan total debit; kalau tidak, submit-nya ditolak oleh cek keseimbangan di
	get_gl_entries().
	"""
	baris = [
		{
			"no_coa": coa_kredit,
			"kegiatan": None,
			"cost_center": cost_center,
			"debit": 0,
			"credit": flt(amount, 2),
			"keterangan": KETERANGAN[sumber],
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
def get_data_costing_kebun(sumber, periode_dari, periode_sampai, company=None, unit=None):
	"""Ketiga tabel sekaligus dari satu kali pembagian.

	Pembagiannya sengaja dihitung sekali di sini: ketiga tabel memandang data
	yang sama, dan mengulang query per tabel cuma memperlambat tombol Ambil Data.
	"""
	semua = bagi_gaji_ke_kegiatan(periode_dari, periode_sampai, company, unit)

	return susun_data_costing_kebun(semua, sumber, company)


def susun_data_costing_kebun(semua, sumber, company):
	"""Ketiga tabel dari pembagian yang sudah terlanjur dihitung."""
	baris = baris_sumber(semua, sumber)

	return {
		"gaji_karyawan": susun_gaji_karyawan(semua, sumber),
		"kegiatan": susun_alokasi_kegiatan(baris, company),
		"closing": susun_closing_kebun(baris, sumber, company),
	}


@frappe.whitelist()
def build_and_submit_costing_kebun(doctype, company, unit, periode_dari, periode_sampai):
	"""Buat dan submit Costing Panen / Costing Perawatan di sisi server.

	Isinya sama persis dengan tombol Ambil Data di form, dipakai waktu
	Accounting Period ditutup.

	Unit yang tidak punya kegiatan sumber ini sama sekali dilewati, dan
	dilewatinya sebelum tabel Closing disusun: unit mill tidak perlu ditinggali
	Costing Panen kosong tiap bulan, juga tidak perlu ikut ditegur soal akun
	6211099 yang cuma dipakai jurnal alokasi. Yang datanya ada tapi belum
	lengkap tetap dibuat supaya kekurangannya kelihatan.
	"""
	doc = frappe.new_doc(doctype)
	doc.company = company
	doc.unit = unit
	doc.periode_dari = periode_dari
	doc.periode_sampai = periode_sampai

	semua = bagi_gaji_ke_kegiatan(periode_dari, periode_sampai, company, unit)
	if not baris_sumber(semua, doc.sumber):
		return None

	doc.isi_data(susun_data_costing_kebun(semua, doc.sumber, company))
	doc.insert(ignore_permissions=True)
	doc.submit()

	return doc.name
