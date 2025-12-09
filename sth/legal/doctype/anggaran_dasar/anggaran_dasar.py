# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class AnggaranDasar(Document):
	
	def validate(self):
		self.clear_akta_list()

	def clear_akta_list(self):
		self.akta = None