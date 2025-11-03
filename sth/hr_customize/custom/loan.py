# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt, nowdate

class Loan:
	def __init__(self, doc, method):
		self.doc = doc
		self.method = method

		match self.method:
			case "validate":
				self.validate_subsidy_component()

	def validate_subsidy_component(self):
		if not self.doc.loan_subsidy:
			return
		
		if not (self.doc.subsidy_component and self.doc.against_subsidy_component):
			frappe.throw("Set Subsidy and Against Subsidy Component for Loan with Subsidy Amount")
            
@frappe.whitelist()
def make_loan_disbursement(
	loan,
	disbursement_amount=0,
	as_dict=0,
	submit=0,
	repayment_start_date=None,
	repayment_frequency=None,
	posting_date=None,
	disbursement_date=None,
	bank_account=None,
	is_term_loan=None,
):
	loan_doc = frappe.get_doc("Loan", loan)
	disbursement_entry = frappe.new_doc("Loan Disbursement")
	disbursement_entry.against_loan = loan_doc.name
	disbursement_entry.subsidy_amount = flt(loan_doc.loan_subsidy - loan_doc.total_subsidy_used)
	disbursement_entry.applicant_type = loan_doc.applicant_type
	disbursement_entry.applicant = loan_doc.applicant
	disbursement_entry.company = loan_doc.company
	disbursement_entry.disbursement_date = posting_date or nowdate()
	disbursement_entry.posting_date = disbursement_date or nowdate()
	disbursement_entry.bank_account = bank_account
	disbursement_entry.repayment_start_date = repayment_start_date
	disbursement_entry.repayment_frequency = repayment_frequency
	disbursement_entry.disbursed_amount = disbursement_amount
	disbursement_entry.is_term_loan = is_term_loan
	disbursement_entry.repayment_schedule_type = loan_doc.repayment_schedule_type

	if loan_doc.repayment_schedule_type != "Line of Credit":
		disbursement_entry.repayment_method = loan_doc.repayment_method

	for charge in loan_doc.get("loan_charges"):
		disbursement_entry.append(
			"loan_disbursement_charges",
			{"charge": charge.charge, "amount": charge.amount, "account": charge.account},
		)

	if submit:
		disbursement_entry.submit()

	if as_dict:
		return disbursement_entry.as_dict()
	else:
		return disbursement_entry