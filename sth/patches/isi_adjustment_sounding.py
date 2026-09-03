import frappe
from frappe.utils import flt

from sth.mill.utils import get_adjustment_stock

# Doctype sounding, item yang disounding, gudangnya, dan apakah stock awalnya
# sudah mencakup mutasi di tanggal prosesnya sendiri.
SOUNDING = (
	("Sounding Stock CPO di BST", "CPO", "Product CPO", True),
	("Sounding Stock Palm Kernel di Bunker Kernel", "Palm Kernel", "Product Palm Kernel", False),
)


def execute():
	"""Isi Stock Awal (Sebelum Adjustment) dan Adjustment di dokumen sounding lama.

	Dua field ini baru, jadi dokumen yang sudah ada menampilkannya nol sampai
	tombol Get Data ditekan — dan di dokumen yang sudah disubmit tombol itu tidak
	bisa dipakai lagi. Keduanya cuma keterangan: stock_awal tidak disentuh, jadi
	produksi, OER, KER, dan Stock Entry-nya tetap seperti semula.

	Aman dijalankan ulang — dokumen yang angkanya sudah cocok dilewati.
	"""
	for doctype, tipe_barang, kategori, termasuk_tanggal_proses in SOUNDING:
		item_code = frappe.db.get_value("Item", {"tipe_barang": tipe_barang})

		if not item_code:
			print("Item {0} tidak ada, {1} dilewati.".format(tipe_barang, doctype))
			continue

		print("{0}: {1} dokumen diperbarui.".format(
			doctype, isi_dokumen(doctype, item_code, kategori, termasuk_tanggal_proses)
		))


def isi_dokumen(doctype, item_code, kategori, termasuk_tanggal_proses):
	gudang = {}
	diperbarui = 0

	for row in frappe.get_all(
		doctype,
		filters={"docstatus": ("<", 2)},
		fields=["name", "unit", "tanggal_proses", "stock_awal",
			"stock_awal_sebelum_adjustment", "adjustment"],
		order_by="tanggal_proses asc, creation asc",
		limit_page_length=0,
	):
		if row.unit not in gudang:
			gudang[row.unit] = frappe.db.get_value(
				"Warehouse", {"unit": row.unit, "warehouse_category": kategori}
			)

		adjustment = get_adjustment_stock(
			item_code, gudang[row.unit], row.unit, doctype, row.tanggal_proses,
			termasuk_tanggal_proses=termasuk_tanggal_proses,
		)
		sebelum = flt(row.stock_awal) - flt(adjustment)

		if (flt(row.adjustment, 3), flt(row.stock_awal_sebelum_adjustment, 3)) == (
			flt(adjustment, 3), flt(sebelum, 3)
		):
			continue

		# Langsung ke kolomnya: dokumennya sudah disubmit dan yang diisi cuma dua
		# field keterangan yang read only di form.
		frappe.db.set_value(doctype, row.name, {
			"adjustment": adjustment,
			"stock_awal_sebelum_adjustment": sebelum,
		}, update_modified=False)
		diperbarui += 1

	frappe.db.commit()

	return diperbarui
