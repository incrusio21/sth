import frappe
from frappe.utils import flt, getdate

from sth.mill.utils import buat_ulang_ste, izinkan_stock_minus

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

	posting_ulang_ste(dokumen)


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


def posting_ulang_ste(dokumen):
	"""Buat ulang Stock Entry dokumen submitted yang STE-nya belum sesuai."""
	perlu = []

	for row in dokumen:
		doc = frappe.get_doc(DOCTYPE, row.name)
		if doc.docstatus == 1 and not ste_sudah_benar(doc):
			perlu.append(doc)

	if not perlu:
		print("Stock Entry Data TBS sudah sesuai semua, dilewati.")
		return

	perlu.sort(key=lambda doc: (getdate(doc.tanggal_produksi), doc.creation))
	dibuat = 0

	with izinkan_stock_minus():
		for urutan, doc in enumerate(perlu, 1):
			dibuat += buat_ulang_ste(doc)

			frappe.db.commit()
			print("[{0}/{1}] {2} selesai.".format(urutan, len(perlu), doc.name))

	print("{0} Stock Entry Data TBS diposting ulang ke tanggal prosesnya.".format(dibuat))

	laporkan_antrian_repost()


def ste_sudah_benar(doc):
	"""Benar kalau tanggal, arah, dan qty STE-nya sudah cocok dengan dokumennya."""
	selisih = flt(doc.total_tbs_restan) - flt(doc.jumlah_tbs_restan)

	ste = frappe.get_all(
		"Stock Entry",
		filters={"references": doc.name, "docstatus": 1},
		fields=["name", "posting_date", "stock_entry_type"],
	)

	if not flt(selisih, 3):
		return not ste

	if len(ste) != 1:
		return False

	ste = ste[0]

	if getdate(ste.posting_date) != getdate(doc.tanggal_produksi):
		return False

	arah = "Material Receipt" if selisih > 0 else "Material Issue"
	if ste.stock_entry_type != arah:
		return False

	qty = frappe.db.get_value("Stock Entry Detail", {"parent": ste.name}, "sum(qty)")

	# Toleransi sekilo per seratus, di bawah presisi qty Stock Entry, supaya
	# patch ini tidak memposting ulang STE yang cuma beda pembulatan.
	return abs(flt(qty) - abs(selisih)) < 0.01


def laporkan_antrian_repost():
	"""Penilaian stok dihitung ulang oleh scheduler, bukan oleh patch ini.

	STE bertanggal mundur bikin ERPNext mengantrikan Repost Item Valuation.
	Menjalankannya di dalam patch bisa memakan waktu berjam-jam dan menahan
	migrate, jadi biar scheduler yang mengerjakan.
	"""
	antri = frappe.db.count("Repost Item Valuation", {"status": ("in", ("Queued", "In Progress"))})
	if antri:
		print("{0} Repost Item Valuation mengantre, nilai stok menyesuaikan setelah scheduler selesai.".format(antri))
