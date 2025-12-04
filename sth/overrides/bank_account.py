import frappe

from erpnext.accounts.doctype.bank_account.bank_account import BankAccount

class BankAccount(BankAccount):
	def autoname(self):
		self.name = self.bank_account_no  