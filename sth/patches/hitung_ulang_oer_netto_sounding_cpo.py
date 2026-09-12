import frappe
from frappe.utils import flt

from sth.mill.doctype.sounding_stock_cpo_di_bst.sounding_stock_cpo_di_bst import (
	SoundingStockCPOdiBST,
)

DOCTYPE = "Sounding Stock CPO di BST"

# Sama dengan precision field oer_netto_1 dan oer_netto_2 di doctype-nya, supaya
# angka hasil patch tidak beda ekor desimal dengan dokumen yang disimpan lewat form.
PRESISI = 2


def execute():
	"""Hitung ulang OER Netto 1 dan 2 di dokumen Sounding CPO yang sudah ada.

	calculate_oer_netto tidak pernah dipanggil dari mana pun sampai perbaikan di
	calculate_totals, jadi dokumen lama menyimpan OER apa adanya dari form — nol
	di dokumen yang diisi lewat tombol Get Data, karena nilai dari respons server
	tidak memicu hitung ulang di sisi form.

	Yang diperbaiki cuma dua kolom itu. Produksi CPO, stock awal, tbs olah, dan
	potongan sortasi dipakai apa adanya dari dokumen dan tidak ikut dihitung
	ulang, jadi Stock Entry maupun jurnalnya tidak tersentuh sama sekali.

	Aman dijalankan ulang — dokumen yang angkanya sudah cocok dilewati. Dokumen
	batal tidak ikut.
	"""
	diperbarui = 0

	for row in frappe.get_all(
		DOCTYPE,
		filters={"docstatus": ("<", 2)},
		fields=["name", "produksi_cpo", "tbs_olah", "potongan_sortasi",
			"oer_netto_1", "oer_netto_2"],
		order_by="tanggal_proses asc, creation asc",
		limit_page_length=0,
	):
		# Rumusnya sengaja dipinjam dari doctype-nya, bukan disalin ke sini:
		# kalau penjaga penyebutnya berubah lagi, tidak ada salinan kedua yang
		# ketinggalan. Methodnya cuma membaca tiga field di bawah ini.
		hitung = frappe._dict(
			produksi_cpo=row.produksi_cpo,
			tbs_olah=row.tbs_olah,
			potongan_sortasi=row.potongan_sortasi,
		)
		SoundingStockCPOdiBST.calculate_oer_netto(hitung)

		netto_1 = flt(hitung.oer_netto_1, PRESISI)
		netto_2 = flt(hitung.oer_netto_2, PRESISI)

		if (flt(row.oer_netto_1, PRESISI), flt(row.oer_netto_2, PRESISI)) == (netto_1, netto_2):
			continue

		# Langsung ke kolomnya: sebagian dokumennya sudah disubmit, dan yang diisi
		# cuma dua field turunan yang read only di form.
		frappe.db.set_value(DOCTYPE, row.name, {
			"oer_netto_1": netto_1,
			"oer_netto_2": netto_2,
		}, update_modified=False)
		diperbarui += 1

	frappe.db.commit()

	print("{0}: OER Netto {1} dokumen dihitung ulang.".format(DOCTYPE, diperbarui))
