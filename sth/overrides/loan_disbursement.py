# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.utils import add_days, cint, flt, getdate

from lending.loan_management.doctype.process_loan_interest_accrual.process_loan_interest_accrual import (
	process_loan_interest_accrual_for_loans,
)

from lending.loan_management.doctype.loan_security_assignment.loan_security_assignment import (
	update_loan_securities_values,
)

from lending.loan_management.doctype.loan_disbursement.loan_disbursement import LoanDisbursement

class STHLoanDisbursement(LoanDisbursement):
    
    def on_trash(self):
        super(LoanDisbursement, self).on_trash()

        if self.docstatus == 0 and self.is_term_loan:
            draft_schedule = self.get_draft_schedule()
            frappe.delete_doc("Loan Repayment Schedule", draft_schedule)
               
    # non aktifkan submit scheduler
    def submit_repayment_schedule(self):
        pass
    
    def cancel_and_delete_repayment_schedule(self):
        filters = {
            "loan": self.against_loan,
            "docstatus": 1,
            "loan_disbursement": self.name,
        }
        if lps := frappe.db.get_value("Loan Repayment Schedule", filters, "name"):
            schedule = frappe.get_doc("Loan Repayment Schedule", lps)
            schedule.reverse_interest_accruals = self.get("reverse_interest_accruals")
            schedule.flags.ignore_links = True
            schedule.cancel()

    def get_schedule_details(self):
        return {
            "doctype": "Loan Repayment Schedule",
            "loan": self.against_loan,
            "repayment_method": self.repayment_method,
            "repayment_start_date": self.repayment_start_date,
            "repayment_periods": self.tenure or 1,
            "posting_date": self.disbursement_date,
            "repayment_frequency": self.repayment_frequency,
            "disbursed_amount": self.disbursed_amount,
            "current_principal_amount": (self.disbursed_amount - self.subsidy_amount),
            "monthly_repayment_amount": self.monthly_repayment_amount
            if self.repayment_method == "Repay Fixed Amount per Period"
            else 0,
            "loan_disbursement": self.name,
        }
    
    def get_values_on_cancel(self, loan_details):
        disbursed_amount = loan_details.disbursed_amount - self.disbursed_amount
        total_payment = loan_details.total_payment
        total_interest_payable = loan_details.total_interest_payable

        if self.is_term_loan:
            if lps := frappe.db.get_value("Loan Repayment Schedule", {"loan_disbursement": self.name, "docstatus": 1}, "name"):
                schedule = frappe.get_doc("Loan Repayment Schedule", lps)
                for data in schedule.repayment_schedule:
                    total_payment -= data.total_payment
                    total_interest_payable -= data.interest_amount
        else:
            total_payment -= self.disbursed_amount

        if (
            loan_details.disbursed_amount > loan_details.loan_amount
            and loan_details.repayment_schedule_type != "Line of Credit"
        ):
            topup_amount = loan_details.disbursed_amount - loan_details.loan_amount
            if topup_amount > self.disbursed_amount:
                topup_amount = self.disbursed_amount

            total_payment = total_payment - topup_amount

        if loan_details.repayment_schedule_type == "Line of Credit":
            status = "Active"
        elif disbursed_amount <= 0:
            status = "Sanctioned"
        elif disbursed_amount >= loan_details.loan_amount:
            status = "Disbursed"
        else:
            status = "Partially Disbursed"

        new_available_limit_amount = loan_details.available_limit_amount + self.disbursed_amount

        new_utilized_limit_amount = loan_details.utilized_limit_amount - self.disbursed_amount

        return (
            disbursed_amount,
            status,
            total_payment,
            total_interest_payable,
            new_available_limit_amount,
            new_utilized_limit_amount,
        )
    
    def get_values_on_submit(self, loan_details):
        precision = cint(frappe.db.get_default("currency_precision")) or 2
        disbursed_amount = self.disbursed_amount + loan_details.disbursed_amount

        if loan_details.repayment_schedule_type == "Line of Credit":
            total_payment = loan_details.total_payment
            total_interest_payable = loan_details.total_interest_payable
        else:
            total_payment = 0
            total_interest_payable = 0

        if loan_details.status in ("Disbursed", "Partially Disbursed") and not loan_details.is_term_loan:
            process_loan_interest_accrual_for_loans(
                posting_date=add_days(self.disbursement_date, -1),
                loan=self.against_loan,
                accrual_type="Disbursement",
            )

        if self.is_term_loan:
            schedule = frappe.get_doc("Loan Repayment Schedule", {"loan_disbursement": self.name})
            for data in schedule.repayment_schedule:
                if getdate(data.payment_date) >= getdate(self.repayment_start_date):
                    total_payment += flt(data.total_payment, precision)
                    total_interest_payable += flt(data.interest_amount, precision)

            total_payment += flt(self.subsidy_amount , precision)
        else:
            total_payment = self.disbursed_amount
        
        if disbursed_amount > loan_details.loan_amount:
            topup_amount = disbursed_amount - loan_details.loan_amount

            if topup_amount < 0:
                topup_amount = 0

            if topup_amount > self.disbursed_amount:
                topup_amount = self.disbursed_amount

        if self.repayment_schedule_type == "Line of Credit":
            status = "Active"
        elif flt(disbursed_amount) >= loan_details.loan_amount:
            status = "Disbursed"
        else:
            status = "Partially Disbursed"

        new_available_limit_amount = (
            loan_details.available_limit_amount - self.disbursed_amount
            if loan_details.maximum_limit_amount
            else 0.0
        )
        new_utilized_limit_amount = (
            loan_details.utilized_limit_amount + self.disbursed_amount
            if loan_details.maximum_limit_amount
            else 0.0
        )

        return (
            disbursed_amount,
            status,
            total_payment,
            total_interest_payable,
            new_available_limit_amount,
            new_utilized_limit_amount,
        )