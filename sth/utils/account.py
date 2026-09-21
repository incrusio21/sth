"""Akun yang harus ada sebelum jurnal otomatis bisa dibuat.

Bagan akun tiap company disalin dari cetakan yang sama, tapi tidak semuanya
disalin di waktu yang sama. Akun 1269999 ALOKASI TBM KE TM misalnya hanya ada
di tiga company — yang kebunnya sudah pernah menaikkan Blok ke TM — sementara
delapan belas sisanya belum punya, dan Blok pertama yang naik TM di sana gagal
dengan pesan bahwa akunnya tidak ditemukan. Yang kurang selalu daun-nya; grup
induknya (12690, 12713) sudah ada di semua company.

Polanya mengikuti `sth.utils.cost_center`: `pastikan_akun` dipanggil yang
membutuhkannya supaya akunnya lahir waktu dipakai, dan `execute` menyiapkan
seluruh akun satu company sekaligus dari baris perintah.
"""

import frappe
from frappe import _

# Akun yang boleh dibuat sendiri oleh kode. Sengaja daftar tertutup: yang
# dibuat otomatis hanya akun yang nomornya, namanya, dan induknya sudah
# ditetapkan di sini, jadi bagan akun tidak bisa tumbuh diam-diam dari salah
# ketik di tempat lain.
AKUN = {
	"1269999": {
		"nama": "ALOKASI TBM KE TM",
		"induk": "12690",
		"root_type": "Asset",
		"keterangan": "Kredit saat Blok TBM naik jadi TM",
	},
	"1271301": {
		"nama": "TANAMAN MENGHASILKAN",
		"induk": "12713",
		"root_type": "Asset",
		"account_type": "Fixed Asset",
		"keterangan": "Debit saat Blok TBM naik jadi TM",
	},
}


def cari_akun(company, nomor):
	"""Nama akun ini di company tersebut, atau None kalau belum ada.

	Dipakai yang cuma mau melihat — preview naik TM misalnya — supaya membuka
	preview tidak menambah akun ke bagan akun company.
	"""
	return frappe.db.get_value("Account", {"account_number": nomor, "company": company}, "name")


def nama_akun_nanti(company, nomor):
	"""Nama akun ini kalau nanti dibuat, dipakai preview waktu akunnya belum ada.

	Susunannya sama dengan yang dipakai ERPNext waktu menamai Account:
	"<nomor> - <nama> - <singkatan company>".
	"""
	_pastikan_dikenal(nomor)

	abbr = frappe.get_cached_value("Company", company, "abbr")

	return "{0} - {1} - {2}".format(nomor, AKUN[nomor]["nama"], abbr)


def pastikan_akun(company, nomor):
	"""Pastikan satu akun ada di company ini, lalu kembalikan namanya.

	Dicari lewat account_number, bukan lewat nama lengkapnya: singkatan company
	bisa berubah dan akun bisa di-rename, sementara nomornya yang menentukan
	akun ini akun yang mana.

	Aman dipanggil berulang, dan aman dipanggil dari dalam transaksi orang lain —
	tidak ada commit di sini. Yang memanggilnya sudah berada di tengah membuat
	jurnal, jadi commit sendiri akan menutup transaksinya sebelum jurnalnya
	sendiri tuntas.
	"""
	_pastikan_dikenal(nomor)

	ada = frappe.db.get_value(
		"Account", {"account_number": nomor, "company": company}, ["name", "is_group"]
	)

	if ada:
		akun, is_group = ada

		if is_group:
			frappe.throw(
				_("Akun {0} ada tapi berupa grup, jadi tidak bisa dipakai untuk menjurnal.").format(
					frappe.bold(akun)
				)
			)

		return akun

	spek = AKUN[nomor]
	induk = frappe.db.get_value(
		"Account", {"account_number": spek["induk"], "company": company, "is_group": 1}, "name"
	)

	if not induk:
		frappe.throw(
			_("Akun grup {0} belum ada di company {1}, jadi akun {2} {3} tidak bisa dibuat di bawahnya.").format(
				frappe.bold(spek["induk"]), frappe.bold(company), nomor, spek["nama"]
			)
		)

	akun = frappe.new_doc("Account")
	akun.account_number = nomor
	akun.account_name = spek["nama"]
	akun.parent_account = induk
	akun.company = company
	akun.is_group = 0
	akun.root_type = spek["root_type"]

	if spek.get("account_type"):
		akun.account_type = spek["account_type"]

	akun.flags.ignore_permissions = True
	akun.insert()

	return akun.name


def execute(company=None, unit=None, nomor=None):
	"""Siapkan akun satu company atau lebih dari baris perintah.

	`company` boleh satu nama atau beberapa dipisah koma. `unit` dipakai kalau
	yang diingat nama unitnya — companynya diambil dari Unit itu. `nomor`
	membatasi ke sebagian akun saja, juga dipisah koma; tanpa itu seluruh isi
	AKUN disiapkan. Tanpa company dan unit sama sekali, semua company disiapkan.

	Akun yang sudah ada dilewati, jadi aman dijalankan ulang.

	    bench --site <site> execute sth.utils.account.execute

	    bench --site <site> execute sth.utils.account.execute
	        --kwargs "{'company': 'PT. KALIMANTAN AGUNG LESTARI', 'nomor': '1269999'}"
	"""
	daftar_company = _pisah(company)

	for nama_unit in _pisah(unit):
		company_unit = frappe.db.get_value("Unit", nama_unit, "company")

		if not company_unit:
			print("Unit {0} tidak ada atau belum punya company, dilewati.".format(nama_unit))
			continue

		if company_unit not in daftar_company:
			daftar_company.append(company_unit)

	if not daftar_company:
		daftar_company = frappe.get_all("Company", pluck="name", order_by="name asc")

	daftar_nomor = _pisah(nomor) or list(AKUN)

	if tak_dikenal := [n for n in daftar_nomor if n not in AKUN]:
		frappe.throw(
			_("Akun {0} tidak dikenal. Yang ada: {1}.").format(
				", ".join(tak_dikenal), ", ".join(AKUN)
			)
		)

	dibuat = 0

	for nama_company in daftar_company:
		if not frappe.db.exists("Company", nama_company):
			print("Company {0} tidak ada, dilewati.".format(nama_company))
			continue

		print("== {0}".format(nama_company))

		for n in daftar_nomor:
			sudah = cari_akun(nama_company, n)
			hasil = pastikan_akun(nama_company, n)

			print("   {0:10} {1:45} {2}".format(
				"sudah ada" if sudah else "DIBUAT", hasil, AKUN[n]["keterangan"]))

			if not sudah:
				dibuat += 1

	frappe.db.commit()
	print("{0} akun dibuat.".format(dibuat))

	return dibuat


def _pastikan_dikenal(nomor):
	if nomor not in AKUN:
		frappe.throw(
			_("Akun {0} tidak ada di daftar akun yang boleh dibuat otomatis.").format(nomor)
		)


def _pisah(nilai):
	"""Argumen bench yang boleh berisi satu nama, beberapa dipisah koma, atau list."""
	if not nilai:
		return []

	daftar = nilai.split(",") if isinstance(nilai, str) else list(nilai)

	return [n.strip() for n in daftar if n and n.strip()]
