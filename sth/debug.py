import frappe
from frappe import _
def debug():
	no_doc = "CB-2026-0003"
	frappe.db.sql(""" DELETE FROM `tabPDO NON PDO Table` WHERE parent = "PDO-00070" and idx = 5 """.format())
	# frappe.db.sql(""" UPDATE `tabPurchase Invoice` SET docstatus=0 WHERE name = "{}" """.format(no_doc))
	frappe.db.sql(""" DELETE FROM `tabPayment Ledger Entry` WHERE voucher_no = "{}" """.format(no_doc))
	frappe.db.sql(""" DELETE FROM `tabGL Entry` WHERE voucher_no = "{}" """.format(no_doc))
	frappe.get_doc("Payment Entry",no_doc).on_submit()

def debug_gl():
	no_doc = "CB-2026-0003"
	# frappe.db.sql(""" DELETE FROM `tabStock Ledger Entry` WHERE voucher_no = "{}" """.format(no_doc))
	frappe.db.sql(""" UPDATE `tabCosting Bengkel` SET docstatus=0 WHERE name = "{}" """.format(no_doc))
	frappe.db.sql(""" DELETE FROM `tabPayment Ledger Entry` WHERE voucher_no = "{}" """.format(no_doc))
	frappe.db.sql(""" DELETE FROM `tabGL Entry` WHERE voucher_no = "{}" """.format(no_doc))
	frappe.get_doc("Costing Bengkel",no_doc).save()

def debug_bkm():
	lis = frappe.db.sql(""" SELECT name FROM `tabBuku Kerja Mandor Traksi` WHERE docstatus = 1 """)
	for row in lis:
		no_doc = row[0]
		frappe.db.sql(""" DELETE FROM `tabPayment Ledger Entry` WHERE voucher_no = "{}" """.format(no_doc))
		frappe.db.sql(""" DELETE FROM `tabGL Entry` WHERE voucher_no = "{}" """.format(no_doc))
		frappe.get_doc("Buku Kerja Mandor Traksi",no_doc).on_submit()
	
def debug_zero():
	# frappe.db.sql(""" UPDATE `tabPengeluaran Barang` SET docstatus=0, workflow_state="Butuh Persetujuan 1" WHERE name = "PB-020726-0002" """)
	frappe.get_doc("Nota Piutang","NDP-072026-00002").on_submit()
	# frappe.db.sql(""" UPDATE `tabPengeluaran Barang` SET docstatus=1 WHERE name = "PB-100626-0001" """)

def debug_ap():
	no_doc="TEST JUNI - TML"
	# frappe.db.sql(""" UPDATE `tabAccounting Period` SET docstatus=0, workflow_state="Draft" WHERE name = "{}" """.format(no_doc))
	from sth.overrides.accounting_period import create_costing_bengkel_on_submit
	create_costing_bengkel_on_submit(frappe.get_doc("Accounting Period",no_doc),"on_submit")

def debug_list():
	li = frappe.db.sql(""" SELECT name FROM `tabDelivery Order` WHERE docstatus = 1 and grand_total > 0 """)
	for row in li:
		no_doc = row[0]
		# frappe.db.sql(""" DELETE FROM `tabStock Ledger Entry` WHERE voucher_no = "{}" """.format(no_doc))
		frappe.db.sql(""" DELETE FROM `tabPayment Ledger Entry` WHERE voucher_no = "{}" """.format(no_doc))
		frappe.db.sql(""" DELETE FROM `tabGL Entry` WHERE voucher_no = "{}" """.format(no_doc))
		frappe.get_doc("Delivery Order",no_doc).on_submit()

def rename_item(dry_run=False):
	frappe.rename_doc("Item Group","30102","31102")
	frappe.rename_doc("Item Group","30201","31201")
	frappe.rename_doc("Item Group","30202","31202")
	frappe.rename_doc("Item Group","30203","31203")
	frappe.rename_doc("Item Group","30301","31301")
	frappe.rename_doc("Item Group","30302","31302")
	frappe.rename_doc("Item Group","30303","31303")
	frappe.rename_doc("Item Group","30304","31304")
	frappe.rename_doc("Item Group","30305","31305")
	frappe.rename_doc("Item Group","30401","31401")
	frappe.rename_doc("Item Group","30402","31402")
	frappe.rename_doc("Item Group","30403","31403")
	frappe.rename_doc("Item Group","30404","31404")
	frappe.rename_doc("Item Group","30405","31405")