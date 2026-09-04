import frappe
from frappe.utils import flt, getdate

from sth.mill.utils import buat_ulang_ste_sounding, izinkan_stock_minus

DOCTYPE = "Sounding Stock CPO di BST"


def execute():
	"""Posting ulang Stock Entry sounding CPO ke tanggal prosesnya.

	Dua kali meleset. Mula-mula posting_date dipetakan dari field tanggal tapi
	validate_posting_time menimpanya kembali dengan hari ini selama
	set_posting_time belum dinyalakan, sehingga penerimaan CPO tercatat di hari
	STE-nya dibuat. Setelah itu dibetulkan, tanggalnya masih field tanggal —
	kapan soundingnya dicatat, biasanya sehari sesudah produksinya — padahal
	produksinya milik hari prosesnya, seperti yang sudah berlaku di Sounding
	Palm Kernel. Sekarang keduanya sama-sama memakai tanggal_proses.

	Angka soundingnya sendiri tidak disentuh. Yang dibetulkan cuma tanggal
	STE-nya, dan karena tanggal Stock Entry tidak bisa diubah setelah submit,
	caranya membatalkan yang lama lalu membiarkan create_ste membuat yang baru.

	Dokumen diurutkan menurut tanggal dan di-commit satu per satu, jadi kalau
	ada yang gagal patch berhenti tapi yang sudah beres tidak ikut hangus. Aman
	dijalankan ulang: dokumen yang tanggal STE-nya sudah benar dilewati.
	"""
	dokumen = frappe.get_all(
		DOCTYPE,
		filters={"docstatus": 1},
		fields=["name", "tanggal_proses", "produksi_cpo"],
		order_by="tanggal_proses asc, creation asc",
		limit_page_length=0,
	)

	salah_tanggal = [row.name for row in dokumen if ste_perlu_dibuat_ulang(row)]

	if not salah_tanggal:
		print("Stock Entry sounding CPO sudah sesuai semua, dilewati.")
		return

	dibuat = 0

	with izinkan_stock_minus():
		for urutan, nama in enumerate(salah_tanggal, 1):
			doc = frappe.get_doc(DOCTYPE, nama)
			dibuat += buat_ulang_ste_sounding(doc, doc.produksi_cpo)

			frappe.db.commit()
			print("[{0}/{1}] {2} selesai.".format(urutan, len(salah_tanggal), nama))

	print("{0} Stock Entry sounding CPO dibuat ulang di tanggal prosesnya, {1} dokumen diperiksa.".format(
		dibuat, len(salah_tanggal)))

	laporkan_antrian_repost()


def ste_perlu_dibuat_ulang(row):
	"""Dokumen yang Stock Entry aktifnya tidak sesuai dokumennya.

	Dua-duanya soal Stock Entry yang sudah terlanjur ada, jadi yang dokumennya
	belum punya Stock Entry sama sekali tidak disentuh — membuatkannya di luar
	urusan patch ini.

	Selain tanggal, ikut disaring dokumen berproduksi nol atau minus yang punya
	Stock Entry aktif. Submit biasa tidak pernah membuatkannya, dan sounding CPO
	berproduksi minus jumlahnya banyak; membiarkannya berarti ada Material Issue
	sebesar angka minus itu menggantung di gudang.
	"""
	ste = frappe.db.get_value(
		"Stock Entry",
		{"references": row.name, "docstatus": 1},
		"posting_date",
	)

	if not ste:
		return False

	if flt(row.produksi_cpo) <= 0:
		return True

	return getdate(ste) != getdate(row.tanggal_proses)


def laporkan_antrian_repost():
	"""Penilaian stok dihitung ulang oleh scheduler, bukan oleh patch ini.

	STE bertanggal mundur bikin ERPNext mengantrikan Repost Item Valuation.
	Menjalankannya di dalam patch bisa memakan waktu berjam-jam dan menahan
	migrate, jadi biar scheduler yang mengerjakan.
	"""
	antri = frappe.db.count("Repost Item Valuation", {"status": ("in", ("Queued", "In Progress"))})
	if antri:
		print("{0} Repost Item Valuation mengantre, nilai stok menyesuaikan setelah scheduler selesai.".format(antri))
