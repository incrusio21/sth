# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BudgetKebunTahunan(Document):
	
	def validate(self):
		self.set_estimasi_upah()
	
	def set_estimasi_upah(self):
		fields = "pembibitan_detail" if self.is_bibitan else "perawatan_detail"
		self.set(fields, [])

def on_doctype_update():
	frappe.db.add_unique("Budget Kebun Tahunan", ["unit", "periode_budget"], constraint_name="unique_unit_periode")
