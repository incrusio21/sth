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
		# Kurs dan nilai mata uang company diisi di sini, tidak bisa mengandalkan
		# Payment Entry mengisinya sendiri: validate() di sth.overrides.payment_entry
		# menggantikan validate() bawaan ERPNext tanpa super(), sehingga
		# set_exchange_rate() dan set_amounts() tidak pernah jalan. PE yang dibuat
		# lewat form lolos karena payment_entry.js menghitungnya di browser.
		company_currency = frappe.get_cached_value("Company", self.company, "default_currency")
		paid_from_currency = self.get_account_currency(self.expense_account, company_currency)
		paid_to_currency = self.get_account_currency(self.debit_to, company_currency)

		pe = frappe.get_doc({
			"doctype": "Payment Entry",
			"unit": self.unit,
			"payment_type": "Internal Transfer",
			"posting_date": self.posting_date,
			"company": self.company,
			"paid_amount": self.disbursement_amount,
			"received_amount": self.disbursement_amount,
			"base_paid_amount": self.disbursement_amount,
			"base_received_amount": self.disbursement_amount,
			"source_exchange_rate": 1,
			"target_exchange_rate": 1,
			"paid_from": self.expense_account,
			"paid_to": self.debit_to,
			"paid_from_account_currency": paid_from_currency,
			"paid_to_account_currency": paid_to_currency,
			"reference_doctype": self.doctype,
			"reference_docname": self.name,
			"remarks": f"Pencairan Loan Bank - {self.name}",
			"tipe_transfer": "Loan Bank"
		})
		pe.insert()
		pe.submit()

		# Link back to this document
		frappe.db.set_value(self.doctype, self.name, "payment_voucher", pe.name)

	def get_account_currency(self, account, company_currency):
		"""Mata uang akun, dipastikan sama dengan mata uang company.

		Kurs di atas dipatok 1, jadi akun bermata uang lain akan menghasilkan nilai
		rupiah yang salah tanpa ketahuan. Lebih baik ditolak di sini.
		"""
		currency = frappe.get_cached_value("Account", account, "account_currency") or company_currency

		if currency != company_currency:
			frappe.throw(
				frappe._("Akun {0} bermata uang {1}, berbeda dengan mata uang company ({2}). "
				  "Pencairan Loan Bank hanya mendukung akun bermata uang sama.").format(
					frappe.bold(account), frappe.bold(currency), frappe.bold(company_currency)
				)
			)

		return currency

def make_disbursement_loan(data):
	doc = frappe.get_doc(data)
	doc.insert()