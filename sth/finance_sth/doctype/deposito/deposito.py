# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt
import math
import frappe

from frappe.model.document import Document
from frappe.utils import add_months, date_diff
from frappe.model.mapper import get_mapped_doc

class Deposito(Document):
	
	def validate(self):
		self.calculate_deposito_interest_table()

	def on_submit(self):
		if not self.deposito_interest_table:
			frappe.throw("Mohon lakukan perhitungan deposito dengan benar sehingga menghasilkan data tdi tabel")
		self.make_deposito_interest()

	def on_cancel(self):
		if not self.deposito_interest_table:
			frappe.throw("Mohon lakukan perhitungan deposito dengan benar sehingga menghasilkan data tdi tabel")
		self.make_deposito_interest()

	def calculate_deposito_interest_table(self):
		self.deposito_interest_table = []
		start_date = self.value_date
		end_date = self.value_date

		for i in range(0, int(self.tenor)):
			end_date = add_months(end_date, 1)
			days = date_diff(end_date, start_date)
			self.calculate_interest_permonth(start_date, end_date, days)
			start_date= end_date

	def calculate_interest_permonth(self, value_date, maturity_date, days):
		deposit_amount = self.deposit_amount
		interest = self.interest / 100
		tax = self.tax / 100
		year_days = self.year_days
		interest_amount = deposit_amount * interest * days / year_days
		tax_amount = interest_amount * tax
		total = interest_amount - tax_amount

		self.append("deposito_interest_table", {
			"posting_date": self.posting_date,
			"deposito_amount": deposit_amount,
			"interest": self.interest,
			"tax": self.tax,
			"value_date": value_date,
			"maturity_date": maturity_date,
			"day_in_months": days,
			"interest_amount": interest_amount,
			"tax_amount": tax_amount,
			"total": total,
			"grand_total": total,
			"outstanding_amount": total,
			"debit_to": frappe.db.get_value("Company", self.company, "default_deposito_debit_account"),
			"expense_account": frappe.db.get_value("Company", self.company, "default_deposito_expense_account")
		})

	def make_deposito_interest(self):
		for row in self.deposito_interest_table:
			values = {
				"doctype": "Deposito Interest",
				"company": self.company,
				"unit": self.unit,
				"posting_date": row.posting_date,
				"value_date": row.value_date,
				"maturity_date": row.maturity_date,
				"day_in_months": row.day_in_months,
				"deposito_amount": row.deposito_amount,
				"interest": row.interest,
				"tax": row.tax,
				"interest_amount": row.interest_amount,
				"tax_amount": row.tax_amount,
				"total": row.total,
				"grand_total": row.grand_total,
				"outstanding_amount": row.outstanding_amount,
				"cost_center": row.cost_center,
				"debit_to": row.debit_to,
				"expense_account": row.expense_account,
				"reference_doc": "Deposito",
				"reference_name": self.name,
				"reference_detail_doc": row.doctype,
				"reference_detail_name": row.name,
			}

			doc = frappe.get_doc(values)
			doc.insert(ignore_permissions=True)
			doc.submit()
			row.deposito_interest = doc.name
			row.db_update_all()

		self.db_update_all()

	def cancel_deposito_intreset(self):
		for row in self.deposito_interest_table:
			doc = frappe.get_doc("Deposito Interest", row.deposito_interest)
			doc.cancel()

@frappe.whitelist()
def make_payment_entry(source_name, target_doc=None):
	def post_process(source, target):
		receivable_customer = frappe.db.get_single_value("Payment Settings", "receivable_customer")
		customer_name = frappe.db.get_value("Customer", receivable_customer, "customer_name")
		company = frappe.db.get_value("Company", source.company, "*")
		account_currency = frappe.db.get_value("Account", source.debit_to, "account_currency")

		target.payment_type = "Receive"
		target.party_type = "Customer"
		target.party = receivable_customer
		target.party_name = customer_name
		target.paid_amount = source.outstanding_amount
		target.paid_from_account_currency = account_currency
		target.paid_to_account_currency = company.default_currency
		target.append("references", {
			"reference_doctype": "Deposito Interest",
			"reference_name": source.name,
			"total_amount": source.grand_total,
			"outstanding_amount": source.outstanding_amount,
			"allocated_amount": source.outstanding_amount
		})
	doclist = get_mapped_doc(
		"Deposito Interest",
		source_name,
		{
			"Deposito Interest": {
				"doctype": "Payment Entry",
				"field_map": {
					"debit_to": "paid_from",
				}
			}
		},
  		target_doc,
		post_process,
	)
 
	return doclist	