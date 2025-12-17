# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.naming import getseries
from sth.controllers.accounts_controller import AccountsController

class DividenTransaction(AccountsController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._expense_account = "debit_to"

	def autoname(self):
		prefix = (
			f"RDVD-{self.company}-"
			if self.transaction_type == "Receive"
			else f"SDVD-{self.company}-"
		)
		self.name = prefix + getseries(prefix, 5)

	def validate(self):
		if self.transaction_type == "Receive":
			self._party_type = "Customer"
			self._expense_account = "credit_to"
			self._party_account_field = "debit_to"
			self.customer = frappe.db.get_single_value("Payment Settings", "receivable_customer")
			self.payment_term = None
		else:
			self.set_missing_value()

	def on_submit(self):
		self.make_gl_entry()

	def on_cancel(self):
		super().on_cancel()
		self.make_gl_entry()