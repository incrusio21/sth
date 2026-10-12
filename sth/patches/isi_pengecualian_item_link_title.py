import frappe


# Doctype yang di item_link_formatter.js dulu selalu menampilkan kode Item.
# Material Request tidak ada di sini: barisnya sudah dibuat
# isi_pengaturan_link_title, dan kalau sudah dihapus dari master jangan dipasang
# lagi.
DOCTYPE_KODE_ITEM = [
	"BOM",
	"Delivery Note",
	"Delivery Order",
	"Pick List",
	"Proposal",
	"Purchase Invoice",
	"Purchase Order",
	"Purchase Receipt",
	"Quotation",
	"Request for Quotation",
	"Retur Ke Supplier",
	"Sales Order",
	"Stock Entry",
	"Subcontracting Order",
	"Supplier Quotation",
]


def execute():
	"""Pindahkan aturan kode Item dari item_link_formatter.js ke Pengaturan Link Title.

	Sejak formatter Item ikut tabel pengecualian master, doctype di atas akan
	berubah jadi menampilkan nama barang kalau tidak punya baris. Baris yang sudah
	ada — untuk Item atau untuk semua link — dilewati, jadi aman diulang.
	"""
	doc = frappe.get_single("Pengaturan Link Title")
	sudah = {(d.di_doctype, d.document_type or "") for d in doc.pengecualian}

	tambah = False
	for di_doctype in DOCTYPE_KODE_ITEM:
		if (di_doctype, "Item") in sudah or (di_doctype, "") in sudah:
			continue
		if not frappe.db.exists("DocType", di_doctype):
			continue

		doc.append("pengecualian", {"di_doctype": di_doctype, "document_type": "Item"})
		tambah = True

	if tambah:
		doc.save(ignore_permissions=True)
