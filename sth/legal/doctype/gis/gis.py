# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt
from frappe.model.document import Document


class GIS(Document):
	def validate(self):
		self.validate_total_lahan_and_tanam()

	def validate_total_lahan_and_tanam(self):
		self.total_lahan = flt(self.lahan_inti) + flt(self.lahan_plasma)
		if self.luas_tanam > self.total_lahan:
			frappe.throw("Luas tanam can't exceed Total Lahan")