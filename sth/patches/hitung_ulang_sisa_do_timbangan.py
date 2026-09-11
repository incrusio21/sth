import frappe
from frappe.utils import cstr

from sth.mill.doctype.timbangan.timbangan import format_sisa, hitung_sisa_do


def execute():
	"""Hitung ulang Sisa DO dan Sisa DO 2 di Timbangan yang sudah ada.

	Kedua field itu dulu cuma diisi JS waktu field DO-nya diubah, jadi angkanya
	berhenti di keadaan saat timbangannya dibuat: Delivery Note berikutnya yang
	memakan DO yang sama menaikkan delivered_qty tanpa pernah menurunkan sisa
	yang tampil. Mulai sekarang sisa ditulis ulang tiap DN disubmit atau
	dibatalkan; patch ini yang membereskan dokumen lama.

	Yang ditulis cuma keterangan — qty_do, qty_do_2, dan Delivery Note-nya tidak
	disentuh, jadi tidak ada stok atau jurnal yang bergerak.

	Aman dijalankan ulang: baris yang angkanya sudah cocok dilewati.
	"""
	sisa_do = {}
	diperbarui = 0

	for row in frappe.get_all(
		"Timbangan",
		filters={"docstatus": ("!=", 2)},
		or_filters=[["do_no", "is", "set"], ["no_do_2", "is", "set"]],
		fields=["name", "do_no", "no_do_2", "kode_barang", "sisa_do", "sisa_do_2"],
		limit_page_length=0,
	):
		nilai = {}

		for fieldname, do_no in (("sisa_do", row.do_no), ("sisa_do_2", row.no_do_2)):
			# DO yang memang tidak diisi dibiarkan apa adanya, tidak ditimpa nol.
			if not do_no or not row.kode_barang:
				continue

			kunci = (do_no, row.kode_barang)
			if kunci not in sisa_do:
				sisa_do[kunci] = format_sisa(hitung_sisa_do(do_no, row.kode_barang))

			if cstr(row.get(fieldname)) != cstr(sisa_do[kunci]):
				nilai[fieldname] = sisa_do[kunci]

		if not nilai:
			continue

		# Langsung ke kolomnya: sebagian timbangannya sudah disubmit dan yang
		# diisi cuma field keterangan yang read only di form.
		frappe.db.set_value("Timbangan", row.name, nilai, update_modified=False)
		diperbarui += 1

	frappe.db.commit()

	print("Sisa DO diperbarui di {0} Timbangan.".format(diperbarui))
