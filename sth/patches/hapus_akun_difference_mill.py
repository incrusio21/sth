import frappe


def execute():
	"""Hapus doctype Akun Difference Mill.

	Tabel itu sempat dipasang di Mill Settings (commit 25760692) lalu diganti
	tabel Akun Difference Produksi Mill di STH Accounting Settings, yang akunnya
	per tipe item. Site yang sempat migrate di antara keduanya masih menyimpan
	doctype dan tabelnya.
	"""
	if frappe.db.exists("DocType", "Akun Difference Mill"):
		frappe.delete_doc("DocType", "Akun Difference Mill", force=True, ignore_missing=True)
