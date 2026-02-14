# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc

class Dividen(Document):
	def validate(self):
		if self.company_one == self.company_two:
			frappe.throw(f"Company 1 dan Company 2 tidak boleh sama")

	def on_submit(self):
		self.make_dividen_transaction()

	def make_dividen_transaction(self):
		values = [
			{
				"doctype": "Dividen Transaction",
				"transaction_type": "Sent",
				"company": self.company_one,
				"unit": self.unit_one,
				"bank": self.bank_one,
				"bank_account": self.bank_account_one,
				"employee": frappe.db.get_single_value("Payment Settings", "internal_employee"),
				"grand_total": self.total,
				"posting_date": self.date,
				"outstanding_amount": self.total,
				"ref_dividen": self.name,
				"credit_to": self.payable_account,
				"debit_to": self.equity_account
			},
			{
				"doctype": "Dividen Transaction",
				"transaction_type": "Receive",
				"company": self.company_two,
				"unit": self.unit_two,
				"bank": self.bank_two,
				"bank_account": self.bank_account_two,
				"customer": frappe.db.get_single_value("Payment Settings", "receivable_customer"),
				"grand_total": self.total,
				"posting_date": self.date,
				"outstanding_amount": self.total,
				"ref_dividen": self.name,
				"credit_to": self.income_account,
				"debit_to": self.receivable_account
			}
		]
		field_ref = {
			"Sent": "dividen_transaction_payment",
			"Receive": "dividen_transaction_receive"
		}
		for val in values:
			doc = frappe.get_doc(val)
			doc.save()
			doc.submit()

			self.db_set(field_ref.get(doc.transaction_type), doc.name)

@frappe.whitelist()
def make_payment_entry(source_name, target_doc=None, type=None):
	account_type = "debit_to" if type == "Receive" else "credit_to"
	paid_type = "paid_from" if type == "Receive" else "paid_to"
	s_name = frappe.db.get_value("Dividen Transaction", {"ref_dividen": source_name, "transaction_type": type}, "name")
	
	def post_process(source, target):
		party_type = "Customer" if type == "Receive" else "Employee"
		payment_type = "Receive" if type == "Receive" else "Internal Transfer"
		field_default_party_type = "receivable_customer" if party_type == "Customer" else "internal_employee"
		default_party = frappe.db.get_single_value("Payment Settings", field_default_party_type)
		field_party_name = "customer_name" if party_type == "Customer" else "employee_name"

		party_name = frappe.db.get_value(party_type, default_party, field_party_name)
		company = frappe.db.get_value("Company", source.company, "*")
		account_currency = frappe.db.get_value("Account", source.debit_to, "account_currency")

		target.payment_type = payment_type
		target.party_type = party_type
		target.party = default_party
		target.party_name = party_name
		target.paid_amount = source.grand_total
		target.bank_account = source.bank_account
		target.paid_from_account_currency = account_currency
		target.paid_to_account_currency = company.default_currency

		if type == "Sent":
			target.paid_to = source.credit_to
			target.paid_from = frappe.get_doc("Unit", source.unit).bank_account

		target.internal_employee = 1 if party_type == "Employee" else 0
		target.append("references", {
			"reference_doctype": "Dividen Transaction",
			"reference_name": source.name,
			"total_amount": source.grand_total,
			"outstanding_amount": source.outstanding_amount,
			"allocated_amount": source.grand_total
		})

	doclist = get_mapped_doc(
		"Dividen Transaction",
		s_name,
		{
			"Dividen Transaction": {
				"doctype": "Payment Entry",
				"field_map": {
					account_type: paid_type,
				}
			}
		},
  		target_doc,
		post_process,
	)
 
	return doclist


def update_dividen_payment_entry(pe, method):
	for ref in pe.references:
		if ref.reference_doctype not in ("Dividen Transaction"):
			continue
		doc = frappe.get_doc(ref.reference_doctype, ref.reference_name)
		doc.payment_entry = pe.name if method == "on_submit" else None
		doc.db_update_all()

		field_ref = {
			"Sent": "payment_entry_sent",
			"Receive": "payment_entry_receive"
		}

		frappe.db.set_value("Dividen", doc.ref_dividen, field_ref.get(doc.transaction_type), pe.name)
