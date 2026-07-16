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
	li = frappe.db.sql(""" SELECT name FROM `tabStation Master` """)
	for row in li:
		no_doc = row[0]
		# frappe.db.sql(""" DELETE FROM `tabStock Ledger Entry` WHERE voucher_no = "{}" """.format(no_doc))
		# frappe.db.sql(""" DELETE FROM `tabPayment Ledger Entry` WHERE voucher_no = "{}" """.format(no_doc))
		# frappe.db.sql(""" DELETE FROM `tabGL Entry` WHERE voucher_no = "{}" """.format(no_doc))
		frappe.get_doc("Station Master",no_doc).create_cost_centers()

def debug_listb():
	li = frappe.db.sql(""" SELECT name FROM `tabStock Entry` WHERE name = "MAT-STE-2026-00090" """)
	for row in li:
		no_doc = row[0]
		doc = frappe.get_doc("Stock Entry",no_doc)
		for row_item in doc.items:
			if row_item.custom_alat_berat_dan_kendaraan:
				row_item.cost_center = "{} - {}".format(row_item.custom_alat_berat_dan_kendaraan, frappe.get_doc("Company",doc.company).abbr)
				row_item.db_update()
				frappe.db.commit()	

		frappe.db.sql(""" DELETE FROM `tabStock Ledger Entry` WHERE voucher_no = "{}" """.format(no_doc))
		frappe.db.sql(""" DELETE FROM `tabPayment Ledger Entry` WHERE voucher_no = "{}" """.format(no_doc))
		frappe.db.sql(""" DELETE FROM `tabGL Entry` WHERE voucher_no = "{}" """.format(no_doc))
		frappe.get_doc("Stock Entry",no_doc).on_submit()


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

def submit_timbangan():

	doc = frappe.get_doc("Timbangan","TBG-9518")
	doc.make_dn()

import frappe

def debug_user():
	frappe.set_user("tpre.em01@sthgroup.com")  # impersonate user itu

	from frappe.desk.desktop import get_workspace_sidebar_items
	result = get_workspace_sidebar_items()
	# import json
	# print(json.dumps(result, indent=2))

def check_alur_user():
	frappe.set_user("tpre.em01@sthgroup.com")

	# 1. Lihat semua DocType yang tergabung di module "Procurement STH"
	doctypes = frappe.get_all("DocType", filters={"module": "Procurement STH"}, pluck="name")
	print(doctypes)

	# 2. Cek apakah user punya permission read ke salah satu doctype itu
	for dt in doctypes:
		print(dt, "->", frappe.has_permission(dt, "read"))

	# 3. Cek role yang dimiliki user
	print(frappe.get_roles("tpre.em01@sthgroup.com"))

def debug_panen_k():
	no_doc = "PPK-00003"
	frappe.db.sql(""" DELETE FROM `tabEmployee Payment Log` WHERE voucher_no = "{}" """.format(no_doc))
	# frappe.db.sql(""" DELETE FROM `tabRecap Panen by Blok` WHERE blok = "A24s" """.format(no_doc))
	
	doc = frappe.get_doc("Pengajuan Panen Kontanan", no_doc)
	doc.on_submit()