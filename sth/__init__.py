__version__ = "0.0.1"

from typing import TYPE_CHECKING, Any

import frappe
from frappe import _

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