import frappe

from frappe.custom.doctype.custom_field.custom_field import create_custom_field

DOCTYPE = "Payroll Entry"
FIELDNAME = "supplier_potongan"


def execute():
	"""Field Supplier Potongan di Payroll Entry, untuk akun potongan bertipe Payable.

	Potongan BPJS karyawan mendarat di Hutang BPJS, akun bertipe Payable, dan
	ERPNext menolak GL Entry tanpa party di akun begitu. Sejak accrual dijurnal
	per akun komponen, akun itu ikut kena - sebelum ada field ini, seluruh
	accrual-nya berhenti dengan "Supplier is required against Payable account".

	Isinya dipakai party_akun_potongan di sth/overrides/payroll_entry.py untuk
	semua akun Payable di payroll itu. Tidak dijadikan wajib di form: payroll
	yang potongannya tidak menyentuh akun Payable tidak perlu mengisinya, dan
	yang menyentuh sudah ditegur waktu jurnalnya disusun, lengkap dengan nama
	akunnya.
	"""
	if frappe.db.exists("Custom Field", {"dt": DOCTYPE, "fieldname": FIELDNAME}):
		return

	create_custom_field(DOCTYPE, {
		"fieldname": FIELDNAME,
		"label": "Supplier Potongan",
		"fieldtype": "Link",
		"options": "Supplier",
		"insert_after": "payroll_payable_account",
		"description": (
			"Lawan jurnal untuk potongan yang akunnya bertipe Payable, misalnya "
			"Hutang BPJS. Kosongkan kalau potongan periode ini tidak menyentuh "
			"akun seperti itu."
		),
	}, ignore_validate=True)
