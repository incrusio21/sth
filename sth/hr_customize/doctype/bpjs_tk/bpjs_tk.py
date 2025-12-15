# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import json

import frappe, erpnext
from frappe import scrub
from frappe.model.document import Document

from erpnext.accounts.general_ledger import merge_similar_entries

from sth.controllers.accounts_controller import AccountsController

class BPJSTK(AccountsController):

	def validate(self):
		self.set_missing_value()

	def on_submit(self):
		self.make_gl_entry()

	def on_cancel(self):
		super().on_cancel()
		self.make_gl_entry()

	def get_gl_entries(self):
		gl_entries = []

		self.make_bpjs_expense_gl_entry(gl_entries)
		self.make_bpjs_credit_gl_entry(gl_entries)

		gl_entries = merge_similar_entries(gl_entries)

		return gl_entries

	def make_bpjs_expense_gl_entry(self, gl_entries):
		cost_center = erpnext.get_default_cost_center(self.company)
		credit_or_debit = "debit"

		self.all_expense_account = set()

		expense = json.loads(self.expense_total)
		for progmam, value in expense.items():
			self.all_expense_account.add(value["expense_account"])
			
			gl_entries.append(
				self.get_gl_dict(
					{
						"account": value["expense_account"],
						"against": self.get(scrub(self._party_type)) or self.credit_to,
						credit_or_debit: value["total"],
						f"{credit_or_debit}_in_account_currency": value["total"],
						"cost_center": cost_center		
					},
					item=self,
				)
			)

	def make_bpjs_credit_gl_entry(self, gl_entries):
		cost_center = erpnext.get_default_cost_center(self.company)
		credit_or_debit = "credit"
		gl_entries.append(
			self.get_gl_dict(
				{
					"account": self.credit_to,
					"against": ",".join(self.all_expense_account),
					credit_or_debit: self.grand_total,
					f"{credit_or_debit}_in_account_currency": self.grand_total,
					"party_type": self._party_type,
                    "party": self.get(scrub(self._party_type)),
					"cost_center": cost_center		
				},
				item=self,
			)
		)