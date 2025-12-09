# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from sth.finance_sth.doctype.disbursement_loan.disbursement_loan import make_disbursement_loan

class LoanBank(Document):
	def validate(self):
		self.process_disbursement()
		self.process_installment()

	def process_disbursement(self):
		for row in self.disbursements:
			create_disbursement(row)
			update_disbursement(row)
		
		cond = {
			"reference_doc": "Loan Bank",
			"reference_name": self.name,
		}
		disbursements = frappe.db.get_all("Disbursement Loan", filters=cond, fields="*")
		for d in disbursements:
			delete_disbursement(d)
	
	def process_installment(self):
		for row in self.installments:
			create_installment(row)
			update_installment(row)
		cond = {
			"reference_doc": "Loan Bank",
			"reference_name": self.name,
		}
		installments = frappe.db.get_all("Installment Loan", filters=cond, fields="*")
		for d in installments:
			delete_installment(d)


def create_disbursement(loan_bank):
	if not frappe.db.exists("Disbursement Loan", loan_bank.disbursement_number):
		values = {
			"doctype": "Disbursement Loan",
			"disbursement_number": loan_bank.disbursement_number,
			"disbursement_date": loan_bank.disbursement_date,
			"disbursement_amount": loan_bank.disbursement_amount,
			"due_days": loan_bank.due_days,
			"reference_doc": "Loan Bank",
			"reference_name": loan_bank.parent,
			"reference_doc_detail": loan_bank.doctype,
			"reference_name_detail": loan_bank.name,
		}
		disbursement_loan = frappe.get_doc(values)
		disbursement_loan.insert(
			ignore_permissions=True
		)


def update_disbursement(loan_bank):
	doc_type = "Disbursement Loan"
	if frappe.db.exists(doc_type, loan_bank.disbursement_number):
		doc = frappe.get_doc(doc_type, loan_bank.disbursement_number)
		check_fields = [
			"disbursement_date",
			"disbursement_amount",
		]

		if is_doc_changed(doc, loan_bank, check_fields):
			doc.disbursement_date = loan_bank.disbursement_date
			doc.disbursement_amount = loan_bank.disbursement_amount
			doc.db_update_all()

def is_doc_changed(old_doc, new_doc, fields):
    for field in fields:
        if old_doc.get(field) != new_doc.get(field):
            return True
    return False

def delete_disbursement(disbursements):
	cond = {
		"disbursement_number": disbursements.disbursement_number,
		"name": disbursements.reference_name_detail,
	}
	if not frappe.db.exists(disbursements.reference_doc_detail, cond):
		frappe.db.delete("Disbursement Loan", disbursements.disbursement_number)

def create_installment(loan_bank):
	if not frappe.db.exists("Installment Loan", loan_bank.disbursement_number):
		values = {
			"doctype": "Installment Loan",
			"disbursement_number": loan_bank.disbursement_number,
			"disbursement_amount": loan_bank.disbursement_amount,
			"disbursement_date": loan_bank.disbursement_date,
			"payment_date": loan_bank.payment_date,
			"installment_month": loan_bank.installment_month,
			"principal": loan_bank.principal,
			"loan_interest": loan_bank.loan_interest,
			"interest_amount": loan_bank.interest_amount,
			"payment_total": loan_bank.payment_total,
			"reference_doc": "Loan Bank",
			"reference_name": loan_bank.parent,
			"reference_doc_detail": loan_bank.doctype,
			"reference_name_detail": loan_bank.name,
		}
		disbursement_loan = frappe.get_doc(values)
		disbursement_loan.insert(
			ignore_permissions=True
		)


def update_installment(loan_bank):
	doc_type = "Installment Loan"
	if frappe.db.exists(doc_type, loan_bank.disbursement_number):
		doc = frappe.get_doc(doc_type, loan_bank.disbursement_number)
		check_fields = [
			"payment_date",
			"installment_month",
			"principal",
			"loan_interest",
			"interest_amount",
			"payment_total",
			"disbursement_amount",
			"disbursement_date",
		]

		if is_doc_changed(doc, loan_bank, check_fields):
			doc.payment_date = loan_bank.payment_date
			doc.installment_month = loan_bank.installment_month
			doc.principal = loan_bank.principal
			doc.loan_interest = loan_bank.loan_interest
			doc.interest_amount = loan_bank.interest_amount
			doc.payment_total = loan_bank.payment_total
			doc.disbursement_amount = loan_bank.disbursement_amount
			doc.disbursement_date = loan_bank.disbursement_date
			doc.db_update_all()

def delete_installment(installments):
	cond = {
		"disbursement_number": installments.disbursement_number,
		"name": installments.reference_name_detail,
	}
	if not frappe.db.exists(installments.reference_doc_detail, cond):
		frappe.db.delete("Installment Loan", installments.disbursement_number)