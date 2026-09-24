import frappe


def execute():
	"""Isi Jumlah TBS Restan (restan_setelah_adjustment) Data TBS yang sudah ada.

	Field-nya baru, jadi setiap dokumen lama lahir dengan nol padahal Grand
	Total TBS-nya sudah memuat restan awal dan adjustment stok. Nilainya cuma
	penjumlahan dua angka yang sudah tersimpan, jadi ditulis langsung lewat SQL
	tanpa menghitung ulang apa pun; hitung_ulang_rantai yang mengurus kalau
	angka dasarnya sendiri perlu dibetulkan. Aman diulang.
	"""
	frappe.db.sql("""
		update `tabData TBS`
		set restan_setelah_adjustment = ifnull(jumlah_tbs_restan, 0) + ifnull(adjustment_stok, 0)
		where ifnull(restan_setelah_adjustment, 0) != ifnull(jumlah_tbs_restan, 0) + ifnull(adjustment_stok, 0)
	""")
