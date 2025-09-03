# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BudgetKebunTahunan(Document):
	pass

def on_doctype_update():
	frappe.db.add_unique("Budget Kebun Tahunan", ["unit", "periode_budget"], constraint_name="unique_unit_periode")
