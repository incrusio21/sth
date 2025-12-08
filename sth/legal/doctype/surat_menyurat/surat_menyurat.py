# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class SuratMenyurat(Document):
	
	def validate(self):
		self.update_status_document()

	def update_status_document(self):
		file_uploaded = "Belum" if not self.file_surat else "Sudah"
		self.status = f"{file_uploaded} Upload"
