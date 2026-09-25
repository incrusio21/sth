# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class DokumenPerijinan(Document):
	def autoname(self):
		if self.is_group == 1:
			self.name = self.company
		else:
			self.name = self.nama_perijinan
