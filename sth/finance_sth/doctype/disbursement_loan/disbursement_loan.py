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
		self.payment_term = None

	def on_submit(self):
	# 	self.make_gl_entry()
		self.make_payment_entry()

	def before_cancel(self):
	# 	super().on_cancel()
	# 	self.make_gl_entry()
		frappe.get_doc("Payment Entry", self.payment_voucher).cancel()

	def make_payment_entry(self):
		pe = frappe.get_doc({
			"doctype": "Payment Entry",
			"unit": self.unit,
			"payment_type": "Internal Transfer",
			"posting_date": self.posting_date,
			"company": self.company,
			"paid_amount": self.disbursement_amount,
			"received_amount": self.disbursement_amount,
			"paid_from": self.expense_account,
			"paid_to": self.debit_to,
			"paid_from_account_currency": frappe.get_value("Account", self.expense_account, "account_currency"),
			"paid_to_account_currency": frappe.get_value("Account", self.debit_to, "account_currency"),
			"reference_doctype": self.doctype,
			"reference_docname": self.name,
			"remarks": f"Pencairan Loan Bank - {self.name}",
		})
		pe.insert()
		pe.submit()
		
		# Link back to this document
		frappe.db.set_value(self.doctype, self.name, "payment_voucher", pe.name)

def make_disbursement_loan(data):
	doc = frappe.get_doc(data)
	doc.insert()