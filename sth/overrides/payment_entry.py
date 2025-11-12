import frappe

import erpnext
from erpnext.accounts.doctype.payment_entry.payment_entry import get_reference_details

from hrms.overrides.employee_payment_entry import (
	EmployeePaymentEntry, 
	get_reference_details_for_employee
)

class PaymentEntry(EmployeePaymentEntry):
	def get_valid_reference_doctypes(self):
		from sth.hr_customize import get_payment_settings
		
		doc_ref = []
		for d in get_payment_settings("reference"):
			if d.party_type != self.party_type:
				continue
			
			doc_ref.extend(d.doctype_ref.split("\n"))

		return doc_ref