# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PlantationMandorSetting(Document):
	pass

def on_doctype_update():
	frappe.db.add_unique("Plantation Mandor Setting", ["voucher_type", "employee_field"], constraint_name="uniqe_employe_voucher")