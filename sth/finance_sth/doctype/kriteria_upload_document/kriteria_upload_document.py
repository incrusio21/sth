# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class KriteriaUploadDocument(Document):
	
	def validate(self):
		self.update_status_document()

	def update_status_document(self):
		doc_meta = frappe.get_meta(self.voucher_type)
		if not doc_meta.get_field("document_status"):
			return
		
		status = "Complete"
		for d in self.file_upload:
			if not d.upload_file:
				status = "Incomplete"
				break
			
		frappe.db.set_value(self.voucher_type, self.voucher_no, "document_status", status)