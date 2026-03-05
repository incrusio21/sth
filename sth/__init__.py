__version__ = "0.0.1"

from typing import TYPE_CHECKING, Any

import frappe
from frappe import _
from frappe.query_builder import Tuple

from erpnext.controllers import status_updater

status_updater.status_map["Proposal"] = [
	["Draft", None],
	[
		"To Receive and Bill",
		"eval:self.per_received < 100 and self.per_billed < 100 and self.docstatus == 1",
	],
	["To Bill", "eval:self.per_received >= 100 and self.per_billed < 100 and self.docstatus == 1"],
	[
		"To Receive",
		"eval:self.per_received < 100 and self.per_billed == 100 and self.docstatus == 1",
	],
	[
		"Completed",
		"eval:self.per_received >= 100 and self.per_billed == 100 and self.docstatus == 1",
	],
	["Delivered", "eval:self.status=='Delivered'"],
	["Cancelled", "eval:self.docstatus==2"],
	["On Hold", "eval:self.status=='On Hold'"],
	["Closed", "eval:self.status=='Closed' and self.docstatus != 2"],
]

status_updater.status_map["BAPP"] = [
	["Draft", None],
	["To Bill", "eval:self.per_billed == 0 and self.docstatus == 1"],
	["Partly Billed", "eval:self.per_billed > 0 and self.per_billed < 100 and self.docstatus == 1"],
	[
		"Completed",
		"eval:(self.per_billed == 100 and self.docstatus == 1)",
	],
	["Cancelled", "eval:self.docstatus==2"],
	["Closed", "eval:self.status=='Closed' and self.docstatus != 2"],
]

if TYPE_CHECKING:
	from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip


from hrms.payroll.doctype.salary_slip import salary_slip_loan_utils

@salary_slip_loan_utils.if_lending_app_installed
def set_loan_repayment(doc: "SalarySlip"):
	from lending.loan_management.doctype.loan_repayment.loan_repayment import calculate_amounts

	doc.total_loan_repayment = 0
	doc.total_interest_amount = 0
	doc.total_principal_amount = 0

	if not doc.get("loans", []):
		loan_details = _get_loan_details(doc)

		for loan in loan_details:
			amounts = calculate_amounts(loan.name, doc.end_date)

			if amounts["payable_amount"]:
				doc.append(
					"loans",
					{
						"loan": loan.name,
						"repayment_start_date": loan.repayment_start_date,
						"monthly_subsidy_component": loan.monthly_subsidy_component,
						"total_payment": amounts["payable_amount"],
						"interest_amount": amounts["interest_amount"],
						"principal_amount": amounts["payable_principal_amount"],
						"loan_account": loan.loan_account,
						"interest_income_account": loan.interest_income_account,
					},
				)
	if not doc.get("loans"):
		doc.set("loans", [])

	for payment in doc.get("loans", []):
		amounts = calculate_amounts(payment.loan, doc.end_date)
		total_amount = amounts["payable_amount"]

		if payment.total_payment > total_amount:
			frappe.throw(
				_(
					"""Row {0}: Paid amount {1} is greater than pending accrued amount {2} against loan {3}"""
				).format(
					payment.idx,
					frappe.bold(payment.total_payment),
					frappe.bold(total_amount),
					frappe.bold(payment.loan),
				)
			)

		doc.total_interest_amount += payment.interest_amount
		doc.total_principal_amount += payment.principal_amount
		doc.total_loan_repayment += payment.total_payment


def _get_loan_details(doc: "SalarySlip") -> dict[str, Any]:
	loan_details = frappe.get_all(
		"Loan",
		fields=["name", "repayment_start_date", "monthly_subsidy_component", "interest_income_account", "loan_account", "loan_product", "is_term_loan"],
		filters={
			"applicant": doc.employee,
			"docstatus": 1,
			"repay_from_salary": 1,
			"company": doc.company,
			"status": ("!=", "Closed"),
		},
	)
	return loan_details

salary_slip_loan_utils.set_loan_repayment = set_loan_repayment
salary_slip_loan_utils._get_loan_details = _get_loan_details

from erpnext.accounts.doctype.payment_entry import payment_entry

def get_references_outstanding_amount(references=None):
	"""
	Fetch accurate outstanding amount of `References`.\n
	    - If `Payment Term` is set, then fetch outstanding amount from `Payment Schedule`.
	    - If `Payment Term` is not set, then fetch outstanding amount from `References` it self.

	Example: {(reference_doctype, reference_name, payment_term): outstanding_amount, ...}
	"""
	if not references:
		return

	refs_with_payment_term = payment_entry.get_outstanding_of_references_with_payment_term(references) or {}
	refs_with_proposal_payment_term = get_outstanding_of_references_with_proposal_payment_term(references) or {}
	refs_without_payment_term = payment_entry.get_outstanding_of_references_with_no_payment_term(references) or {}

	return {**refs_with_payment_term, **refs_with_proposal_payment_term, **refs_without_payment_term}

def get_outstanding_of_references_with_proposal_payment_term(references=None):
	"""
	Fetch outstanding amount of `References` which have `Payment Term` set.\n
	Example: {(reference_doctype, reference_name, payment_term): outstanding_amount, ...}
	"""
	if not references:
		return

	refs = {
		(row.reference_doctype, row.reference_name, row.payment_term)
		for row in references
		if row.reference_doctype and row.reference_name and row.payment_term
	}

	if not refs:
		return
	
	PS = frappe.qb.DocType("Proposal Schedule")

	response = (
		frappe.qb.from_(PS)
		.select(PS.parenttype, PS.parent, PS.payment_term, PS.outstanding)
		.where(Tuple(PS.parenttype, PS.parent, PS.payment_term).isin(refs))
	).run(as_dict=True)

	if not response:
		return

	return {(row.parenttype, row.parent, row.payment_term): row.outstanding for row in response}

payment_entry.get_references_outstanding_amount = get_references_outstanding_amount