# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class TutupBukuFisik(Document):
	pass

def create_tutup_buku(from_date,to_date):
	doc = frappe.new_doc("Tutup Buku Fisik")
	doc.company = frappe.defaults.get_global_default("company")
	doc.periode = "Monthly"
	doc.from_date = from_date
	doc.to_date = to_date

	warehouses = frappe.get_all("Warehouse",{"company": doc.company,"is_group": 0},pluck="name")
	for warehouse in warehouses:
		doc.append("list_gudang",{
			"warehouse": warehouse
		})

	doc.save()
	doc.submit()

@frappe.whitelist()
def open_doc(name):
	frappe.db.set_value("Tutup Buku Fisik",name,"docstatus",0)
