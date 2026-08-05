import frappe
from frappe.utils import flt

DOCTYPE = "Buku Kerja Mandor Perawatan"


def execute():
	"""Keluarkan nilai material dari jurnal BKM Perawatan yang terlanjur terbentuk.

	make_gl_entry dulu memposting grand_total, padahal calculate_grand_total
	menjumlahkan semua field ber-"amount" termasuk material_amount. Nilai material
	sendiri sudah dijurnal Stock Entry "Material Used" ke akun kegiatan yang sama,
	jadi akun itu terdebit dua kali. Nilainya dikembalikan ke upah + premi saja.

	Hanya menyentuh baris yang nilainya memang persis grand_total dokumennya —
	baris yang sudah benar atau yang pernah disesuaikan manual dibiarkan.
	"""
	bkm = frappe.get_all(
		DOCTYPE,
		filters={"docstatus": ["<", 2], "material_amount": [">", 0]},
		fields=["name", "grand_total", "hasil_kerja_amount", "hasil_kerja_premi_amount"],
	)

	if not bkm:
		return

	dokumen = {row.name: row for row in bkm}

	entries = frappe.get_all(
		"GL Entry",
		filters={
			"voucher_type": DOCTYPE,
			"voucher_no": ["in", list(dokumen)],
			"is_cancelled": 0,
		},
		fields=["name", "voucher_no", "debit", "credit"],
	)

	diperbaiki = 0

	for entry in entries:
		doc = dokumen[entry.voucher_no]
		nilai = flt(doc.hasil_kerja_amount) + flt(doc.hasil_kerja_premi_amount)

		# sisi baris dikenali dari kolom mana yang terisi
		if flt(entry.debit):
			kolom, lama = "debit", flt(entry.debit)
		elif flt(entry.credit):
			kolom, lama = "credit", flt(entry.credit)
		else:
			continue

		# hanya baris yang membawa nilai lama yang keliru itu yang ditulis ulang
		if abs(lama - flt(doc.grand_total)) >= 0.01:
			continue

		frappe.db.set_value(
			"GL Entry",
			entry.name,
			{kolom: nilai, "{0}_in_account_currency".format(kolom): nilai},
			update_modified=False,
		)
		diperbaiki += 1

	if diperbaiki:
		print("{0} GL Entry {1} disesuaikan tanpa nilai material".format(diperbaiki, DOCTYPE))
