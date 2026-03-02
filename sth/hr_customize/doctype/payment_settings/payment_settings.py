# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class PaymentSettings(Document):
	
	def get_outstanding_doctype(self):
		if not getattr(self, "_outstanding_doctype", None):
			self._outstanding_doctype = self.outstanding_doctype.split("\n")

		return self._outstanding_doctype
	 
