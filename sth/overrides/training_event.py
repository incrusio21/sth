import frappe
from frappe.utils import flt, nowdate

import erpnext
from erpnext.accounts.doctype.payment_entry.payment_entry import (
	PaymentEntry,
	get_bank_cash_account,
	get_reference_details,
)
from erpnext.accounts.utils import get_account_currency
from erpnext.setup.utils import get_exchange_rate

from hrms.hr.doctype.expense_claim.expense_claim import get_outstanding_amount_for_claim

@frappe.whitelist()
def get_purchase_invoice_for_training_event(dt, dn, party_amount=None, bank_account=None, bank_amount=None):
	doc = frappe.get_doc(dt, dn)

	pi = frappe.new_doc("Purchase Invoice")
	pi.supplier = doc.supplier

	return pi

@frappe.whitelist()
def get_payment_entry_for_training_event(dt, dn, party_amount=None, bank_account=None, bank_amount=None):
	doc = frappe.get_doc(dt, dn)

	# party_account = get_party_account(doc)
	# party_account_currency = get_account_currency(party_account)
	payment_type = "Pay"
	# grand_total, outstanding_amount = get_grand_total_and_outstanding_amount(
	# 	doc, party_amount, party_account_currency
	# )

	# # bank or cash
	# bank = get_bank_cash_account(doc, bank_account)
	bank_account = frappe.get_doc("Bank Account", {"company": doc.company})
	company = frappe.get_doc("Company", doc.company)

	# paid_amount, received_amount = get_paid_amount_and_received_amount(
	# 	doc, party_account_currency, bank, outstanding_amount, payment_type, bank_amount
	# )

	pe = frappe.new_doc("Payment Entry")
	pe.payment_type = payment_type
	pe.company = doc.company
	pe.posting_date = nowdate()
	pe.party_type = "Supplier"
	pe.party = doc.get("supplier")
	pe.party_name = frappe.get_doc("Supplier", doc.get("supplier")).supplier_name
	pe.bank_account = bank_account.name
	pe.paid_from = bank_account.account
	pe.paid_to = company.default_payable_account
	pe.paid_amount = doc.custom_grand_total_costing
	pe.received_amount = doc.custom_grand_total_costing

	pe.append(
		"references",
		{
			"reference_doctype": dt,
			"reference_name": dn,
			# "bill_no": doc.get("bill_no"),
			# "due_date": doc.get("due_date"),
			"total_amount": doc.custom_grand_total_costing,
			"outstanding_amount": doc.custom_grand_total_costing,
			"allocated_amount": doc.custom_grand_total_costing,
		},
	)

	pe.setup_party_account_field()
	pe.set_missing_values()
	pe.set_missing_ref_details()

	return pe