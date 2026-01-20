# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
from frappe.utils import flt

class NaturaMultiplier(Document):
	def validate(self):
		self.total_multiplier()

	def total_multiplier(self):
		if "T" in self.pkp:
			self.partner_multiplier = 0

		if "0" in self.pkp:
			self.child_multiplier = 0

		self.multiplier = flt(
			self.employee_multiplier +
			self.partner_multiplier +
			self.child_multiplier
		)
