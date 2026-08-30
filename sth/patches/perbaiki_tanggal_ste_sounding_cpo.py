import frappe
from frappe.utils import getdate

from sth.mill.utils import buat_ulang_ste_sounding, izinkan_stock_minus

DOCTYPE = "Sounding Stock CPO di BST"


def execute():
	"""Posting ulang Stock Entry sounding CPO ke tanggal soundingnya.

	posting_date sudah dipetakan dari tanggal, tapi validate_posting_time
	menimpanya kembali dengan hari ini selama set_posting_time belum dinyalakan.
	Akibatnya seluruh penerimaan CPO tercatat di hari STE-nya dibuat, bukan di
	tanggal soundingnya, dan laporan stok per tanggal jadi meleset.

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
		fields=["name", "tanggal"],
		order_by="tanggal asc, creation asc",
		limit_page_length=0,
	)

	salah_tanggal = [row.name for row in dokumen if ste_salah_tanggal(row)]

	if not salah_tanggal:
		print("Tanggal Stock Entry sounding CPO sudah benar semua, dilewati.")
		return

	dibuat = 0

	with izinkan_stock_minus():
		for urutan, nama in enumerate(salah_tanggal, 1):
			doc = frappe.get_doc(DOCTYPE, nama)
			dibuat += buat_ulang_ste_sounding(doc, doc.produksi_cpo)

			frappe.db.commit()
			print("[{0}/{1}] {2} selesai.".format(urutan, len(salah_tanggal), nama))

	print("{0} Stock Entry sounding CPO diposting ulang ke tanggal soundingnya.".format(dibuat))

	laporkan_antrian_repost()


def ste_salah_tanggal(row):
	posting_date = frappe.db.get_value(
		"Stock Entry",
		{"references": row.name, "docstatus": 1},
		"posting_date",
	)

	if not posting_date:
		return False

	return getdate(posting_date) != getdate(row.tanggal)


def laporkan_antrian_repost():
	"""Penilaian stok dihitung ulang oleh scheduler, bukan oleh patch ini.

	STE bertanggal mundur bikin ERPNext mengantrikan Repost Item Valuation.
	Menjalankannya di dalam patch bisa memakan waktu berjam-jam dan menahan
	migrate, jadi biar scheduler yang mengerjakan.
	"""
	antri = frappe.db.count("Repost Item Valuation", {"status": ("in", ("Queued", "In Progress"))})
	if antri:
		print("{0} Repost Item Valuation mengantre, nilai stok menyesuaikan setelah scheduler selesai.".format(antri))
