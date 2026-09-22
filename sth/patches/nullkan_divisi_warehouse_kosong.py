import frappe


def execute():
	"""Divisi Warehouse yang string kosong diubah jadi NULL.

	Form mengirim "" waktu Link Divisi dikosongkan dan Frappe menulisnya apa
	adanya, jadi baris lama campur antara '' dan NULL. Query yang memakai
	`IS NULL` atau LEFT JOIN ke Divisi jadi tidak konsisten.

	Dokumen baru sudah tertutup hook before_validate
	sth.custom.warehouse.kosongkan_divisi_jadi_null; yang tersisa baris lama, dan
	itu yang diurus di sini. Aman dijalankan berulang.
	"""
	jumlah = frappe.db.sql("""
		SELECT COUNT(*)
		FROM `tabWarehouse`
		WHERE divisi IS NOT NULL AND TRIM(divisi) = ''
	""")[0][0]

	if not jumlah:
		print("Divisi Warehouse: tidak ada baris string kosong")
		return

	frappe.db.sql("""
		UPDATE `tabWarehouse`
		SET divisi = NULL
		WHERE divisi IS NOT NULL AND TRIM(divisi) = ''
	""")

	frappe.clear_cache(doctype="Warehouse")

	print(f"Divisi Warehouse: {jumlah} baris diubah dari string kosong jadi NULL")
