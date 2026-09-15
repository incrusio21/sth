import frappe

DOCTYPE = "Mill Master"


def execute():
	"""Isi QR pabrik untuk Mill Master yang sudah telanjur ada.

	QR-nya baru dibuat di before_save, jadi pabrik yang tidak pernah disimpan
	lagi sesudah field ini ditambahkan tidak punya QR sama sekali dan Sounding
	CPO / PK tidak bisa dibuat - field Pabrik di sana memang hanya bisa terisi
	lewat scan.

	Koordinatnya dibiarkan apa adanya, umumnya masih 0, sama seperti sebagian
	baris Detail Station Master yang QR-nya sudah dipakai sehari-hari. Isi QR
	dibangun ulang tiap kali Mill Master disimpan, jadi begitu lat/long diisi
	benar QR-nya ikut berubah sendiri tanpa menjalankan patch ini lagi.
	"""
	diperbarui = 0

	for name in frappe.get_all(DOCTYPE, pluck="name"):
		doc = frappe.get_doc(DOCTYPE, name)

		# Lewat metode dokumennya sendiri supaya isi QR patch dan QR yang dibuat
		# saat simpan tidak pernah beda.
		doc.create_qr_pabrik()

		frappe.db.set_value(DOCTYPE, name, "qr_code", doc.qr_code, update_modified=False)
		diperbarui += 1

	frappe.db.commit()

	print("{0}: QR pabrik dibuat untuk {1} dokumen.".format(DOCTYPE, diperbarui))
