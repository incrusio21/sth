# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PengeluaranBarang(Document):
	def on_submit(self):
		self.create_ste()
	
	def create_ste(self):
		pass