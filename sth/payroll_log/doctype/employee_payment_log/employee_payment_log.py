# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class EmployeePaymentLog(Document):
	
	def validate(self):
		self.get_employee_payment_account()

	def get_employee_payment_account(self):
		self.employee_payment_account = frappe.get_cached_value("Company", self.company, "employee_payment_account")

	def on_update(self):
		self.create_journal_entry()

	def create_journal_entry(self):
		if self.journal_entry:
			return

		if not (self.employee_payment_account and self.kegiatan_account):
			frappe.throw("Please Set Employee Payment Account and Kegiatan Account First")

		je = frappe.new_doc("Journal Entry")
		je.update({
			"company": self.company,
			"posting_date": self.posting_date,
		})

		je.append("account", {
			"account": self.kegiatan_account,
			"debit_in_account_currency": self.amount
		})

		je.append("account", {
			"account": self.employee_payment_account,
			"party_type": "Employee",
			"party": self.employee,
			"debit_in_account_currency": self.amount
		})

		je.submit()

		self.db_set("journal_entry", je.name)
