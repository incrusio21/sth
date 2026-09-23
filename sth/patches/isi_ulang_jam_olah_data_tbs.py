import frappe

from sth.mill.doctype.data_tbs.data_tbs import perbarui_jam_olah


def execute():
	"""Baca ulang jam olah dan kapasitas pabrik seluruh Data TBS dari CBC Monitoring.

	Dua cacat yang sudah telanjur tertulis di dokumen submitted:

	1. CBC Monitoring dibaca tanpa saringan unit, jadi Data TBS bisa memakai jam
	   pabrik lain — DTBS-0083 (TPRM, 18 September) tercatat 920 jam dari
	   CBC/ASRM//00006, padahal CBC/TPRM//00060 hari itu 17,1 jam.
	2. CBC Monitoring yang disubmit sesudah Get Data tidak pernah terbaca —
	   DTBS-0081 (16 September) jam olahnya nol padahal CBC/TPRM//00058 13,2.

	Cuma total_jam_olah dan kapasitas_pabrik yang ditulis. Keduanya tidak masuk
	rantai restan, Stock Entry, maupun tbs olah sounding, jadi tidak ada yang
	perlu diposting ulang. Aman dijalankan ulang: yang sudah cocok dilewati.
	"""
	pasangan = frappe.db.sql("""
		select distinct unit, tanggal_produksi
		from `tabData TBS`
		where docstatus < 2 and unit is not null and tanggal_produksi is not null
		order by unit, tanggal_produksi
	""", as_dict=True)

	diperbarui = 0

	for row in pasangan:
		diperbarui += perbarui_jam_olah(row.unit, row.tanggal_produksi)

	print("{0} Data TBS diperbarui jam olahnya, dari {1} tanggal.".format(diperbarui, len(pasangan)))
