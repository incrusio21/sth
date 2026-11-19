import frappe


def execute():
	"""Kelas BPJS Kesehatan tidak dipakai lagi: Daftar BPJS KES langsung memakai
	satu-satunya program di Set Up BPJS PT. Sync customization tidak menghapus
	field yang hilang dari employee.json, jadi dihapus di sini."""
	nama = "Employee-kelas_bpjs_kesehatan"
	if frappe.db.exists("Custom Field", nama):
		frappe.delete_doc("Custom Field", nama, ignore_permissions=True, force=True)
