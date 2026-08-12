import frappe

from sth.plantation.doctype.buku_kerja_mandor_premi.buku_kerja_mandor_premi import (
	on_doctype_update,
)

DOCTYPE = "Buku Kerja Mandor Premi"
TABLE = "tab{0}".format(DOCTYPE)

# Kunci yang benar-benar dipakai kode. Harus sama persis, termasuk urutannya,
# dengan daftar kolom di on_doctype_update milik doctype-nya.
KOLOM_BENAR = ["employee", "mandor_type", "company", "buku_kerja_mandor", "posting_date"]


def execute():
	"""Buang unique index basi di Buku Kerja Mandor Premi, bentuk ulang yang benar.

	Di site yang sudah lama berjalan ditemukan dua unique index dan tak satu pun
	cocok dengan kode:

	- unique_item_warehouse (employee, posting_date) — namanya milik tabBin
	  bawaan ERPNext, jelas sisa salin-tempel. Ini satu-satunya yang benar-benar
	  menjaga, dan jauh lebih ketat dari yang dimaksud: satu mandor hanya boleh
	  punya satu baris premi per bulan, lintas peran, lintas Panen/Traksi, dan
	  lintas company.
	- uniqe_employe_voucher (employee, company, voucher_type, posting_date) —
	  sisa versi lama waktu doctype ini masih punya field voucher_type. Field-nya
	  sudah tidak ada, dan Frappe tidak pernah membuang kolom, jadi kolomnya kini
	  selalu NULL. Di MariaDB unique index yang memuat NULL tidak pernah dianggap
	  bentrok, jadi index ini sebenarnya sudah mati dan tidak menjaga apa pun.

	frappe.db.add_unique memeriksa *nama* constraint, bukan kolomnya, jadi selama
	masih ada constraint bernama uniqe_employe_voucher, on_doctype_update lewat
	begitu saja dan kolomnya tidak pernah ikut terkoreksi. Karena itu index basi
	perlu dibuang dulu di sini.

	Gejalanya: create_or_update_mandor_premi menyisipkan baris premi, ditolak
	index dua kolom itu walau kombinasi lima kolomnya belum ada, lalu jatuh ke
	blok except yang mencari barisnya memakai mandor_type — dan tidak ketemu,
	karena baris yang bentrok tercatat dengan peran yang lain.
	"""
	if not frappe.db.table_exists(DOCTYPE):
		print("Tabel {0} belum ada, dilewati.".format(DOCTYPE))
		return

	terpasang = kumpulkan_index_unik()
	basi = {nama: kolom for nama, kolom in terpasang.items() if kolom != KOLOM_BENAR}
	sudah_benar = KOLOM_BENAR in terpasang.values()

	if not basi and sudah_benar:
		print("Unique index {0} sudah benar, dilewati.".format(DOCTYPE))
		return

	# Selama index yang lebih ketat masih terpasang, data pasti sudah memenuhi
	# kunci yang benar. Pemeriksaan ini untuk site yang index-nya sudah terlanjur
	# dibuang manual: lebih baik patch berhenti dan melapor daripada menggagalkan
	# seluruh migrate saat add_unique menabrak baris kembar.
	duplikat = cari_duplikat()
	if duplikat:
		print(
			"Ada {0} kombinasi kembar di {1}, index tidak disentuh.".format(
				len(duplikat), DOCTYPE
			)
		)
		print("Rapikan dulu baris berikut, lalu jalankan migrate lagi:")
		for d in duplikat:
			print(
				"  {0} | {1} | {2} | {3} | {4} -> {5} baris".format(
					d.employee, d.mandor_type, d.company,
					d.buku_kerja_mandor, d.posting_date, d.jumlah,
				)
			)
		return

	for nama, kolom in basi.items():
		frappe.db.sql_ddl("ALTER TABLE `{0}` DROP INDEX `{1}`".format(TABLE, nama))
		print("Unique index basi dibuang: {0} ({1}).".format(nama, ", ".join(kolom)))

	if not sudah_benar:
		on_doctype_update()
		print("Unique index dibentuk ulang: {0}.".format(", ".join(KOLOM_BENAR)))


def kumpulkan_index_unik():
	"""Kembalikan {nama_index: [kolom, ...]} untuk semua unique index selain PRIMARY."""
	baris = frappe.db.sql(
		"SHOW INDEX FROM `{0}` WHERE Non_unique = 0".format(TABLE), as_dict=True
	)

	kolom = {}
	for b in baris:
		if b.Key_name == "PRIMARY":
			continue
		kolom.setdefault(b.Key_name, []).append((b.Seq_in_index, b.Column_name))

	return {
		nama: [k for _, k in sorted(urutan)] for nama, urutan in kolom.items()
	}


def cari_duplikat():
	kolom = ", ".join("`{0}`".format(k) for k in KOLOM_BENAR)

	return frappe.db.sql(
		"""
		SELECT {0}, COUNT(*) AS jumlah
		FROM `{1}`
		GROUP BY {0}
		HAVING jumlah > 1
		""".format(kolom, TABLE),
		as_dict=True,
	)
