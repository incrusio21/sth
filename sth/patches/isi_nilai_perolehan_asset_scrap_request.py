import frappe
from frappe.utils import flt


def execute():
	"""Isi Harga Perolehan Discrap untuk pengajuan yang sudah terlanjur disubmit.

	Fieldnya baru ada sesudah pengajuan-pengajuan itu disetujui, dan dokumen
	submitted tidak lewat validate lagi, jadi angkanya akan terus kosong di form
	kalau tidak diisi dari sini.

	Hitungannya sama persis dengan yang dipakai waktu jurnalnya dibuat — harga
	perolehan dikali persentase discrap — jadi pembatalan pengajuan lama tetap
	mengembalikan angka yang sama, baik sebelum maupun sesudah patch ini jalan.
	"""
	if not frappe.db.has_column("Asset Scrap Request", "nilai_perolehan_scrap"):
		return

	pengajuan = frappe.get_all(
		"Asset Scrap Request",
		filters={"nilai_perolehan_scrap": ["in", [0, None]]},
		fields=["name", "gross_purchase_amount", "persentase_scrap"],
	)

	for baris in pengajuan:
		# pengajuan sebelum ada input persentase diperlakukan sebagai scrap penuh,
		# sama seperti di validate
		persentase = flt(baris.persentase_scrap) or 100
		nilai = flt(flt(baris.gross_purchase_amount) * persentase / 100.0, 2)

		if not nilai:
			continue

		frappe.db.set_value(
			"Asset Scrap Request",
			baris.name,
			"nilai_perolehan_scrap",
			nilai,
			update_modified=False,
		)
