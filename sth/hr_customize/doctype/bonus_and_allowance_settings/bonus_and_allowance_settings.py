# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

# import frappe
from frappe import scrub
from frappe.model.document import Document


class BonusandAllowanceSettings(Document):
	
	def get_natura_setting(self, unit):
		unit_setting = self.get("thr_natura_settings", {"unit": unit}) or [{}]
		
		return scrub(unit_setting[0].get("fields") or "Employee Multiplier")

	def get_natura_setting_phk(self, unit):
		unit_setting = self.get("phk_natura_settings", {"unit": unit}) or [{}]
		
		return scrub(unit_setting[0].get("fields") or "Employee Multiplier")
