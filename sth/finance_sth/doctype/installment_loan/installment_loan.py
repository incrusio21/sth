# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from sth.controllers.accounts_controller import AccountsController

class InstallmentLoan(AccountsController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._expense_account = "debit_to"

	def on_submit(self):
		self.set_missing_value()
		self.make_gl_entry()

	def on_cancel(self):
		super().on_cancel()
		self.make_gl_entry()
