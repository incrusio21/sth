import frappe
from frappe.utils import getdate

from sth.mill.doctype.timbangan.timbangan import make_delivery_note
from sth.mill.utils import izinkan_stock_minus

# Timbangan sebelum tanggal ini tidak disentuh: periodenya sudah ditutup dan
# tanggal DN-nya dibiarkan apa adanya.
MULAI = "2026-08-04"


def execute():
	"""Samakan tanggal Delivery Note kiriman timbangan dispatch dengan timbangannya.

	posting_date tidak ikut dipetakan make_delivery_note - di Delivery Note field
	itu no_copy, jadi map_fields melewatinya - dan DN memakai default doctype-nya,
	yaitu hari DN itu dibuat. Timbangan yang bertanggal mundur atau baru disubmit
	keesokan harinya menghasilkan DN yang berbeda hari dengan timbangannya,
	sehingga pengiriman tercatat di tanggal yang salah.

	Tanggal Delivery Note tidak bisa diubah setelah submit, jadi caranya sama
	seperti buat_ulang_ste_sounding: DN lama dibatalkan dan dihapus, lalu dibuat
	ulang lewat make_delivery_note yang sekarang sudah membawa posting_date
	timbangannya. Nomor DN-nya ikut berganti, dan field delivery_note di
	timbangannya diarahkan ke nomor yang baru.

	DN yang sudah dipakai dokumen lain - Sales Invoice yang sudah submit,
	misalnya - tidak bisa dibatalkan; dokumen itu dilewati dan didaftar di akhir
	untuk dibereskan sendiri.

	Tiap timbangan di-commit begitu selesai, jadi kalau ada yang gagal yang sudah
	beres tidak ikut hangus. Aman dijalankan ulang: DN yang tanggalnya sudah sama
	dengan timbangannya dilewati.

	Dijalankan dengan:
		bench --site <site> execute sth.patches.samakan_tanggal_dn_timbangan.execute
	"""
	daftar = frappe.get_all(
		"Timbangan",
		filters={
			"docstatus": 1,
			"type": "Dispatch",
			"posting_date": (">=", getdate(MULAI)),
		},
		fields=[
			"name", "posting_date", "delivery_note", "delivery_note_2",
			"do_no", "no_do_2", "qty_do", "qty_do_2", "netto_2",
		],
		order_by="posting_date asc, creation asc",
		limit_page_length=0,
	)

	perlu = [row for row in daftar if dn_salah_tanggal(row)]

	if not perlu:
		print("Tanggal Delivery Note timbangan dispatch sejak {0} sudah benar semua, dilewati.".format(MULAI))
		return

	dibuat = 0
	gagal = []

	with izinkan_stock_minus():
		for urutan, row in enumerate(perlu, 1):
			try:
				dibuat += buat_ulang_dn_timbangan(row)
			except Exception as e:
				frappe.db.rollback()
				gagal.append((row.name, str(e)))
				print("[{0}/{1}] {2} gagal: {3}".format(urutan, len(perlu), row.name, e))
				continue

			frappe.db.commit()
			print("[{0}/{1}] {2} selesai.".format(urutan, len(perlu), row.name))

	print("{0} Delivery Note dibuat ulang mengikuti tanggal timbangannya.".format(dibuat))

	laporkan_gagal(gagal)
	laporkan_antrian_repost()


def dn_salah_tanggal(row):
	"""Timbangan ini punya DN yang tanggalnya beda dengan tanggal timbangannya."""
	return any(
		beda_tanggal(row.get(fieldname), row.posting_date)
		for fieldname in ("delivery_note", "delivery_note_2")
	)


def beda_tanggal(nama_dn, posting_date):
	if not nama_dn:
		return False

	tanggal_dn = frappe.db.get_value("Delivery Note", nama_dn, "posting_date")

	if not tanggal_dn:
		return False

	return getdate(tanggal_dn) != getdate(posting_date)


def buat_ulang_dn_timbangan(row):
	"""Buat ulang DN timbangan ini yang tanggalnya masih meleset.

	Qty-nya mengikuti create_delivery_notes: DN pertama sebesar qty_do, atau
	netto_2 kalau qty_do kosong; DN kedua sebesar qty_do_2.
	"""
	dibuat = 0

	slot = (
		("delivery_note", row.do_no, row.qty_do or row.netto_2),
		("delivery_note_2", row.no_do_2, row.qty_do_2),
	)

	for fieldname, do_no, qty in slot:
		if not beda_tanggal(row.get(fieldname), row.posting_date):
			continue

		buang_dn(row.get(fieldname))

		baru = make_delivery_note(row.name, do_no=do_no, qty=qty)
		baru.insert()
		baru.submit()

		frappe.db.set_value("Timbangan", row.name, fieldname, baru.name)

		print("  {0}: {1} -> {2} ({3})".format(
			fieldname, row.get(fieldname), baru.name, baru.posting_date
		))

		dibuat += 1

	return dibuat


def buang_dn(nama_dn):
	"""Batalkan lalu hapus DN lama supaya nomornya tidak menyisakan dokumen batal."""
	doc = frappe.get_doc("Delivery Note", nama_dn)

	if doc.docstatus == 1:
		doc.cancel()

	doc.delete()


def laporkan_gagal(gagal):
	"""Daftar timbangan yang DN-nya tidak bisa dibuat ulang.

	Biasanya karena DN-nya sudah dipakai dokumen lain yang masih submit, jadi
	pembatalannya ditolak. Tanggal DN-nya tetap seperti semula.
	"""
	if not gagal:
		return

	print("{0} timbangan gagal, tanggal DN-nya belum berubah:".format(len(gagal)))
	for nama, pesan in gagal:
		print("  {0}: {1}".format(nama, pesan))


def laporkan_antrian_repost():
	"""Penilaian stok dihitung ulang oleh scheduler, bukan oleh patch ini.

	DN bertanggal mundur bikin ERPNext mengantrikan Repost Item Valuation.
	Menjalankannya di dalam patch bisa memakan waktu berjam-jam dan menahan
	migrate, jadi biar scheduler yang mengerjakan.
	"""
	antri = frappe.db.count("Repost Item Valuation", {"status": ("in", ("Queued", "In Progress"))})
	if antri:
		print("{0} Repost Item Valuation mengantre, nilai stok menyesuaikan setelah scheduler selesai.".format(antri))
