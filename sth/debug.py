import frappe
from frappe import _
def debug():
	# frappe.db.sql(""" DELETE FROM `tabPayment Ledger Entry` WHERE voucher_no = "ACC-PINV-2026-00087" """)
	# frappe.db.sql(""" DELETE FROM `tabGL Entry` WHERE voucher_no = "ACC-PINV-2026-00087" """)
	frappe.get_doc("Surat Jalan","SJ-040626-0001").on_submit()
	