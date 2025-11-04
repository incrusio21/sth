# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class TransaksiTHR(Document):
	@frappe.whitelist()
	def get_salary_structure_assignment(self, employee):
		return frappe.db.sql("""
			SELECT
			ssa.base as gaji_pokok
			FROM `tabSalary Structure Assignment` as ssa
			WHERE ssa.employee = %s
			ORDER BY ssa.from_date DESC
			LIMIT 1;
		""", (employee), as_dict=True)
