# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from sth.controllers.accounts_controller import AccountsController

class DisbursementLoan(AccountsController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._party_type = "Customer"
		self._expense_account = "expense_account"
		self._party_account_field = "debit_to"
		self.customer = frappe.db.get_single_value("Payment Settings", "receivable_customer")
		self.payment_term = None

	def on_submit(self):
		self.make_gl_entry()

	def on_cancel(self):
		super().on_cancel()
		self.make_gl_entry()

def make_disbursement_loan(data):
    doc = frappe.get_doc(data)
    doc.insert()