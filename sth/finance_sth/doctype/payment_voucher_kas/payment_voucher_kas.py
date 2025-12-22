# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from sth.controllers.accounts_controller import AccountsController
from frappe.model.mapper import get_mapped_doc

class PaymentVoucherKas(AccountsController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._expense_account = "account"
		
	def validate(self):
		if self.transaction_type == "Masuk":
			self._party_type = "Customer"
			self._expense_account = "account"
			self._party_account_field = "debit_to"
			self.customer = frappe.db.get_single_value("Payment Settings", "receivable_customer")
			self.payment_term = None
		else:
			self.set_missing_value()

	def on_submit(self):
		self.make_gl_entry()
		self.make_payment_entry()

	def on_cancel(self):
		super().on_cancel()
		self.make_gl_entry()

	def make_payment_entry(self):
		account_type = "debit_to" if self.transaction_type == "Masuk" else "credit_to"
		paid_type = "paid_from" if self.transaction_type == "Masuk" else "paid_to"
		
		def post_process(source, target):
			party_type = "Customer" if self.transaction_type == "Masuk" else "Employee"
			payment_type = "Receive" if self.transaction_type == "Masuk" else "Pay"
			field_default_party_type = "receivable_customer" if party_type == "Customer" else "internal_employee"
			default_party = frappe.db.get_single_value("Payment Settings", field_default_party_type)
			field_party_name = "customer_name" if party_type == "Customer" else "employee_name"

			party_name = frappe.db.get_value(party_type, default_party, field_party_name)
			company = frappe.db.get_value("Company", source.company, "*")
			account_currency = frappe.db.get_value("Account", source.debit_to, "account_currency")
			mode_of_payment = frappe.db.get_value("Mode of Payment Account", {"parent": "Cash", "company": self.company}, "*")
			
			target.payment_type = payment_type
			target.party_type = party_type
			target.party = default_party
			target.party_name = party_name
			target.paid_amount = source.outstanding_amount
			target.received_amount = source.outstanding_amount
			target.paid_from_account_currency = account_currency
			target.paid_to_account_currency = company.default_currency
			target.internal_employee = 1 if party_type == "Employee" else 0
			target.paid_from = source.debit_to if party_type == "Customer" else mode_of_payment.default_account
			target.paid_to = source.credit_to if party_type == "Employee" else mode_of_payment.default_account
			target.cost_center = company.cost_center

			target.append("references", {
				"reference_doctype": "Payment Voucher Kas",
				"reference_name": source.name,
				"total_amount": source.outstanding_amount,
				"outstanding_amount": source.outstanding_amount,
				"allocated_amount": source.outstanding_amount,
			})

		doclist = get_mapped_doc(
			"Payment Voucher Kas",
			self.name,
			{
				"Payment Voucher Kas": {
					"doctype": "Payment Entry",
				}
			},
			None,
			post_process,
		)
		doclist.save()
		doclist.submit()

	@frappe.whitelist()
	def set_exchange_rate(self):
		currency_exchange = frappe.db.get_all("Currency Exchange", filters={
			"from_currency": self.currency,
			"to_currency": "IDR"
		}, order_by="date DESC",page_length=1, fields=["exchange_rate"])
		if not currency_exchange:
			return
		self.exchange_rate = currency_exchange[0].exchange_rate