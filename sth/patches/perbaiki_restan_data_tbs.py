import frappe
from frappe.utils import flt

# posting_ulang_ste tinggal di controller Data TBS, bukan di patch ini:
# membatalkan lalu membuat ulang Stock Entry bertanggal mundur juga dipakai
# tombol Hitung Ulang di formnya.
from sth.mill.doctype.data_tbs.data_tbs import posting_ulang_ste

DOCTYPE = "Data TBS"


def execute():
	"""Hitung ulang restan Data TBS dan posting ulang Stock Entry-nya.

	Dua hal yang dibetulkan sekaligus, dua-duanya sudah telanjur terjadi di
	dokumen yang disubmit:

	1. Restan awal dulu dibaca dari saldo Bin waktu tombol Get Data ditekan,
	   padahal Bin baru bergerak waktu Data TBS disubmit. Waktu dokumen 19–24
	   Juli disiapkan harian tapi baru disubmit borongan 25 Juli, semuanya
	   membaca saldo yang sama (42.701,95) dan Stock Entry-nya jadi Material
	   Receipt semua sampai stok TBS menggelembung ke 626.255,04.

	2. Hari tanpa data lori bikin berat rata-rata nol, dan karena restan dihitung
	   sebagai berat rata-rata dikali jumlah lori, seluruh TBS hari itu hilang
	   dari rantai — Grand Total TBS-nya tidak diteruskan jadi restan hari
	   berikutnya.

	Fase satu memperbaiki angka dokumennya, fase dua memposting ulang Stock
	Entry-nya ke tanggal proses dengan selisih yang benar. Dipisah supaya kalau
	pembatalan STE tertahan periode akuntansi yang sudah tutup, angka dokumennya
	tetap sudah benar. Aman dijalankan ulang: dokumen yang angkanya sudah cocok
	dan STE-nya sudah benar dilewati.
	"""
	dokumen = frappe.get_all(
		DOCTYPE,
		filters={"docstatus": ("<", 2)},
		fields=["name", "unit", "tanggal_produksi"],
		order_by="unit asc, tanggal_produksi asc, creation asc",
		limit_page_length=0,
	)

	if not dokumen:
		print("Tidak ada Data TBS, dilewati.")
		return

	diperbaiki = hitung_ulang_dokumen(dokumen)
	print("{0} dari {1} Data TBS dihitung ulang restannya.".format(diperbaiki, len(dokumen)))

	posting_ulang_ste(dokumen, lapor=print)


def hitung_ulang_dokumen(dokumen):
	"""Rantai restan awal tiap unit dari Total TBS Restan dokumen sebelumnya."""
	restan = {}
	diperbaiki = 0

	for row in dokumen:
		doc = frappe.get_doc(DOCTYPE, row.name)
		# Dibulatkan dulu sebelum dibanding: nilai yang dibaca dari kolom decimal
		# selalu beda di digit terakhir dari hasil hitungan float.
		sebelum = angka_restan(doc)

		doc.jumlah_tbs_restan = restan.get(doc.unit, 0)
		doc.calculate_totals()
		restan[doc.unit] = flt(doc.total_tbs_restan)

		if angka_restan(doc) == sebelum:
			continue

		# db_update, bukan save: dokumennya sudah disubmit dan yang diubah cuma
		# angka turunan yang seluruhnya read only di form.
		doc.db_update()
		diperbaiki += 1

	frappe.db.commit()

	return diperbaiki


def angka_restan(doc):
	# Presisi field tidak dipakai: total_tbs_restan presisinya 0 supaya tampil
	# bulat di form, padahal selisih setengah kilo tetap harus ikut dibetulkan.
	return tuple(flt(doc.get(field), 3) for field in (
		"jumlah_tbs_restan", "grand_total_tbs", "berat_rata_rata_tbs",
		"tbs_olah", "tbs_restan", "tbs_loading_ramp", "total_tbs_restan",
	))
