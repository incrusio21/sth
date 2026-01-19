# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class TutupBukuFisik(Document):
	pass

def create_tutup_buku(from_date,to_date,warehouse):
	doc = frappe.new_doc("Tutup Buku Fisik")
	doc.periode = "Monthly"
	doc.from_date = from_date
	doc.to_date = to_date
	doc.warehouse = warehouse

	doc.save()
	doc.submit()