import frappe

DOCTYPE = "Payment Entry"
FIELDNAME = "realisasi_tambahan"


def execute():
	"""Tampilkan centang Realisasi Tambahan dan buang keterangannya.

	Keterangan lama hanya menyebut "baris yang tidak berasal dari PDO", padahal
	penandanya sekarang juga menyala ketika realisasi baris yang justru berasal
	dari PDO melewati plafon penerimanya — lihat set_realisasi_tambahan. Daripada
	menyesatkan pemeriksa, keterangannya dibuang dan cukup labelnya yang bicara.

	Patch tambah_jalur_approval_realisasi_tambahan sudah jalan lebih dulu di site
	yang berjalan, jadi perubahan definisinya di sana tidak akan terpakai lagi.
	"""
	nama = frappe.db.get_value(
		"Custom Field", {"dt": DOCTYPE, "fieldname": FIELDNAME}, "name"
	)

	if not nama:
		print("Custom Field {0} belum ada, dilewati.".format(FIELDNAME))
		return

	frappe.db.set_value("Custom Field", nama, {
		"hidden": 0,
		"description": "",
	})

	frappe.clear_cache(doctype=DOCTYPE)

	print("Centang {0} dibuat tampil dan keterangannya dibuang.".format(FIELDNAME))
