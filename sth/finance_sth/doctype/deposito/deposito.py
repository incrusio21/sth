# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt
import math
import frappe

from frappe.model.document import Document
from frappe.utils import date_diff

from sth.controllers.accounts_controller import AccountsController

class Deposito(AccountsController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._expense_account = "expense_account"
		self._party_account_field = "debit_to"
		self._party_type = "Customer"
		self.customer = frappe.db.get_single_value("Payment Settings", "receivable_customer")

	def validate(self):
		self.calculate_deposito()

	def on_submit(self):
		self.make_gl_entry()

	def on_cancel(self):
		super().on_cancel()
		self.make_gl_entry()

	def calculate_deposito(self):
		self.calculate_tenor()
		interest_amount = self.deposit_amount * (self.interest/100)  * (self.tenor*self.month_days) / self.year_days
		tax_amount = interest_amount * (self.tax/100)
		total = interest_amount - tax_amount
		interest_amount_monthly = self.deposit_amount * (self.interest/100)  * self.month_days / self.year_days
		tax_amount_monthly = interest_amount_monthly * (self.tax/100)
		total_monthly = interest_amount_monthly - tax_amount_monthly
		
		self.interest_amount = interest_amount
		self.tax_amount = tax_amount
		self.total = total
		self.interest_amount_monthly = interest_amount_monthly
		self.tax_amount_monthly = tax_amount_monthly
		self.total_monthly = total_monthly
		self.grand_total = total
		self.outstanding_amount = total

	def calculate_tenor(self):
		tenor = (date_diff(self.maturity_date, self.value_date)+1) / self.month_days
		self.tenor = math.floor(tenor)