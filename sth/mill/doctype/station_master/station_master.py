# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class StationMaster(Document):
	def validate(self):
		from sth.utils.qr_generator import generate_qr_for_doc
		generate_qr_for_doc(self,1)