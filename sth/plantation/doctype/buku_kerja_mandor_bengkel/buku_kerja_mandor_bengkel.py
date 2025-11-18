# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class BukuKerjaMandorBengkel(Document):
	pass

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_employee_traksi_query(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""
			SELECT e.name, e.employee_name
			FROM `tabEmployee` e
			JOIN `tabDesignation` d ON d.name = e.designation
			WHERE d.is_jabatan_traksi = 1
			AND (e.name LIKE %(txt)s OR e.employee_name LIKE %(txt)s)
			LIMIT %(start)s, %(page_len)s
	""", {
			"txt": f"%{txt}%",
			"start": start,
			"page_len": page_len
	})