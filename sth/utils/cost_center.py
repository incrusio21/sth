"""Cost Center induk yang harus ada sebelum dokumen operasional bisa dibuat.

Blok, Alat Berat dan Kendaraan, Data Penyemaian Bibit, dan Station Master
sama-sama membuat Cost Center sendiri waktu disimpan, dan semuanya menggantung
ke satu grup induk per company yang namanya sudah ditetapkan di kode —
"Blok - <singkatan>", "Tahun Tanam - <singkatan>", dan seterusnya. Di company
yang sudah lama dipakai grup itu ada, jadi tidak pernah jadi soal. Di company
baru tidak ada, dan dokumennya gagal disimpan dengan pesan link tidak ketemu
yang tidak menyebut grup mana yang kurang.

Yang di sini menambalnya dari dua arah: `pastikan_induk` dipanggil pembuat Cost
Center-nya sendiri supaya grupnya lahir waktu dibutuhkan, dan `execute`
menyiapkan seluruh grup satu company sekaligus dari baris perintah — berguna
waktu company barunya disiapkan sebelum dokumen pertamanya dibuat.
"""

import frappe
from frappe import _

# Nama grup induk tanpa singkatan company, beserta apa yang digantung di
# bawahnya. Yang memakainya masing-masing doctype, bukan modul ini; daftar ini
# yang membuatnya bisa disiapkan sekaligus.
INDUK = {
	"Blok": "Cost Center per Blok, dipakai Blok yang sudah TM",
	"Tahun Tanam": "Cost Center per tahun tanam, dipakai Blok yang masih TBM",
	"VRA": "Alat berat dan kendaraan, juga Costing Bengkel",
	"Batch Bibit": "Batch penyemaian bibit",
	"Station": "Stasiun pabrik",
}


def root_cost_center(company):
	"""Cost Center paling atas milik company ini.

	Biasanya bernama "<nama company> - <singkatan>", dan itu yang dicoba lebih
	dulu karena paling murah. Company yang akarnya pernah di-rename tidak lagi
	bernama begitu — KEBUN A1 - KAL misalnya — jadi kalau meleset yang dicari
	grup tanpa induk milik company itu.
	"""
	company_doc = frappe.get_cached_doc("Company", company)
	tebakan = "{0} - {1}".format(company_doc.company_name, company_doc.abbr)

	if frappe.db.exists("Cost Center", tebakan):
		return tebakan

	# "is not set", bukan in ("", None): induk akar tersimpan NULL, dan NULL tidak
	# pernah cocok dengan daftar IN — barisnya lolos tanpa bunyi.
	akar = frappe.db.get_value(
		"Cost Center",
		{"company": company, "is_group": 1, "parent_cost_center": ("is", "not set")},
		"name",
		order_by="lft asc",
	)

	if not akar:
		frappe.throw(
			_("Company {0} belum punya Cost Center induk sama sekali.").format(frappe.bold(company))
		)

	return akar


def pastikan_induk(company, nama):
	"""Pastikan satu grup induk ada di company ini, lalu kembalikan namanya.

	Dicari lewat cost_center_name, bukan lewat nama lengkapnya: singkatan company
	bisa berubah dan Cost Center bisa di-rename, sementara yang menentukan grup
	ini grup yang mana tetap namanya sendiri.

	Aman dipanggil berulang, dan aman dipanggil dari dalam transaksi orang lain —
	tidak ada commit di sini. Yang memanggilnya sudah berada di tengah simpan
	dokumen, jadi commit sendiri akan menutup transaksinya sebelum dokumennya
	sendiri tuntas.
	"""
	ada = frappe.db.get_value(
		"Cost Center", {"cost_center_name": nama, "company": company}, ["name", "is_group"]
	)

	if ada:
		induk, is_group = ada

		if not is_group:
			frappe.throw(
				_("Cost Center {0} ada tapi bukan grup, jadi tidak bisa dipakai sebagai induk.").format(
					frappe.bold(induk)
				)
			)

		return induk

	cc = frappe.new_doc("Cost Center")
	cc.cost_center_name = nama
	cc.parent_cost_center = root_cost_center(company)
	cc.company = company
	cc.is_group = 1
	cc.flags.ignore_permissions = True
	cc.insert()

	return cc.name


def execute(company=None, unit=None, induk=None):
	"""Siapkan seluruh Cost Center induk satu company dari baris perintah.

	`company` boleh satu nama atau beberapa dipisah koma. `unit` dipakai kalau
	yang diingat nama unitnya — companynya diambil dari Unit itu. `induk`
	membatasi ke sebagian grup saja, juga dipisah koma; tanpa itu seluruh isi
	INDUK disiapkan.

	Grup yang sudah ada dilewati, jadi aman dijalankan ulang.

	    bench --site <site> execute sth.utils.cost_center.execute
	        --kwargs "{'company': 'PT. KALIMANTAN AGUNG LESTARI'}"

	    bench --site <site> execute sth.utils.cost_center.execute
	        --kwargs "{'unit': 'KJHO', 'induk': 'Blok,Tahun Tanam'}"
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
		frappe.throw(_("Sebutkan company atau unit yang mau disiapkan Cost Center induknya."))

	daftar_induk = _pisah(induk) or list(INDUK)

	if tak_dikenal := [n for n in daftar_induk if n not in INDUK]:
		frappe.throw(
			_("Cost Center induk {0} tidak dikenal. Yang ada: {1}.").format(
				", ".join(tak_dikenal), ", ".join(INDUK)
			)
		)

	dibuat = 0

	for nama_company in daftar_company:
		if not frappe.db.exists("Company", nama_company):
			print("Company {0} tidak ada, dilewati.".format(nama_company))
			continue

		print("== {0} (akar: {1})".format(nama_company, root_cost_center(nama_company)))

		for nama in daftar_induk:
			sudah = frappe.db.exists("Cost Center", {"cost_center_name": nama, "company": nama_company})
			hasil = pastikan_induk(nama_company, nama)

			print("   {0:14} {1:28} {2}".format(
				"sudah ada" if sudah else "DIBUAT", hasil, INDUK[nama]))

			if not sudah:
				dibuat += 1

	frappe.db.commit()
	print("{0} Cost Center induk dibuat.".format(dibuat))

	return dibuat


def _pisah(nilai):
	"""Argumen bench yang boleh berisi satu nama, beberapa dipisah koma, atau list."""
	if not nilai:
		return []

	daftar = nilai.split(",") if isinstance(nilai, str) else list(nilai)

	return [n.strip() for n in daftar if n and n.strip()]
