# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

"""Rincian komponen gaji per akun — satu sumber untuk accrual dan costing.

Sejak accrual Payroll Entry dijurnal per Salary Component dan bukan lagi satu
akun beban gaji, tiga hal harus dilihat sama oleh Payroll Entry dan tiap costing
yang mereclass gaji: komponen mana yang ikut dijurnal, berapa nilainya, dan ke
akun mana. Beda satu saja, akun beban gajinya tidak pernah nol lagi setelah
direclass.

Aturannya ditaruh di satu tempat:

- Earning yang dicentang "Not Include Net Pay" tidak ikut. Itu BPJS beban
  perusahaan dan gross up PPh21: bebannya sudah lahir dari dokumen BPJS TK/Kes
  sendiri, dan nilainya memang tidak menambah net pay.
- Deduction ikut penyaring "Do Not Include In Total", penyaring yang sama yang
  dipakai Salary Slip waktu menghitung total potongan. Kalau tidak sama,
  jurnalnya tidak akan pernah ketemu dengan net pay.
- Akunnya dari tabel Accounts di Salary Component, dicocokkan per company.

Dengan aturan itu berlaku:

	total earning - total deduction = net pay + angsuran pinjaman

karena begitulah Salary Slip menghitung net pay-nya (lihat set_net_pay di
sth/overrides/salary_slip.py). Angsuran pinjaman muncul di ruas kanan karena
Loan Repayment yang mendebit Payroll Payable dibuat terpisah waktu slip
disubmit.
"""

import frappe
from frappe import _
from frappe.utils import flt, get_link_to_form

FIELD_KEGIATAN_KEBUN = "dibagi_ke_kegiatan_kebun"


def rincian_komponen(company, salary_slips, parentfield="earnings", hanya_kegiatan_kebun=False):
	"""Baris komponen tiap slip beserta akunnya.

	Baris bernilai nol dibuang lebih dulu: komponen yang kebetulan nol di
	periode ini tidak perlu ikut ditegur soal akun yang belum diisi.
	"""
	salary_slips = [d for d in (salary_slips or []) if d]
	if not salary_slips:
		return []

	if parentfield == "earnings":
		kondisi = "AND IFNULL(sc.not_include_net_pay, 0) = 0"
	else:
		kondisi = "AND IFNULL(sd.do_not_include_in_total, 0) = 0"

	if hanya_kegiatan_kebun:
		kondisi += " AND IFNULL(sc.`{0}`, 0) = 1".format(FIELD_KEGIATAN_KEBUN)

	rows = frappe.db.sql("""
		SELECT
			ss.name AS salary_slip,
			ss.employee,
			ss.employee_name,
			sd.salary_component,
			sd.amount,
			sca.account
		FROM `tabSalary Slip` ss
		JOIN `tabSalary Detail` sd
			ON sd.parent = ss.name AND sd.parentfield = %(parentfield)s
		JOIN `tabSalary Component` sc ON sc.name = sd.salary_component
		LEFT JOIN `tabSalary Component Account` sca
			ON sca.parent = sd.salary_component AND sca.company = %(company)s
		WHERE ss.name IN %(slips)s
		  AND IFNULL(sd.amount, 0) != 0
		  {kondisi}
	""".format(kondisi=kondisi), {
		"parentfield": parentfield,
		"company": company,
		"slips": tuple(salary_slips),
	}, as_dict=True)

	tanpa_akun = sorted({r.salary_component for r in rows if not r.account})
	if tanpa_akun:
		frappe.throw(
			_("Salary Component berikut belum punya akun untuk company {0} "
			  "(lihat tabel Accounts di masternya): {1}").format(
				frappe.bold(company),
				", ".join(get_link_to_form("Salary Component", d) for d in tanpa_akun),
			),
			title=_("Akun Komponen Belum Diisi"),
		)

	return rows


def per_slip_akun(rows):
	"""Total tiap akun, dikelompokkan per salary slip."""
	hasil = {}
	for r in rows:
		akun = hasil.setdefault(r["salary_slip"], {})
		akun[r["account"]] = akun.get(r["account"], 0) + flt(r["amount"])
	return hasil


def pecah_per_akun(amount, campuran):
	"""Bagi satu nilai mengikuti komposisi akun sebuah pool atau karyawan.

	Dipakai costing waktu yang direclass cuma sebagian dari gaji seseorang —
	misalnya gaji operator bengkel yang dibagi ke beberapa kendaraan. Sisa
	pembulatan ditaruh di akun terbesar supaya jumlah pecahannya persis sama
	dengan nilai yang dibagi.
	"""
	total = sum(flt(v) for v in campuran.values())
	if not flt(amount) or not total:
		return {}

	hasil = {}
	terbagi = 0
	for akun, nilai in campuran.items():
		porsi = flt(flt(amount) * flt(nilai) / total, 2)
		if not porsi:
			continue
		hasil[akun] = porsi
		terbagi += porsi

	if not hasil:
		return hasil

	selisih = flt(flt(amount, 2) - terbagi, 2)
	if selisih:
		terbesar = max(hasil, key=lambda a: hasil[a])
		hasil[terbesar] = flt(hasil[terbesar] + selisih, 2)

	return hasil
