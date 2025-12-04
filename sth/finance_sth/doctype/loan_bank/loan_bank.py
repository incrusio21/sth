# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from sth.finance_sth.doctype.disbursement_loan.disbursement_loan import make_disbursement_loan

class LoanBank(Document):
	def on_update_after_submit(self):
		pass

	def create_disbursement(self):
		for row in self.disbursements:
			pass