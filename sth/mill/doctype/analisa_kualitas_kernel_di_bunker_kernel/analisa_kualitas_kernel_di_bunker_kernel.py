# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class AnalisaKualitasKerneldiBunkerKernel(Document):
	def before_submit(self):
		self.status = "Selesai"