# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.query_builder.functions import Sum

class LoanDisbursement:
    def __init__(self, doc, method):
        self.doc = doc
        self.method = method

        match self.method:
            case "on_submit":
                self.create_subsidy_repayment()
                self.update_subsidy_remaning()
            case "on_cancel":
                self.remove_subsidy_repayment()
                self.update_subsidy_remaning()

    def create_subsidy_repayment(self):
        if not self.doc.subsidy_amount:
            return
        
        from lending.loan_management.doctype.loan.loan import make_repayment_entry

        repayment = make_repayment_entry(
            self.doc.against_loan, self.doc.applicant_type, self.doc.applicant, self.doc.loan_product, self.doc.company, self.doc.name
        )

        repayment.repayment_type = "Principal Adjustment"
        repayment.loan_disbursement = self.doc.name
        repayment.subsidy_component = self.doc.subsidy_component
        repayment.against_subsidy_component = self.doc.against_subsidy_component
        repayment.amount_paid = self.doc.subsidy_amount
        repayment.is_subsidy = 1

        repayment.submit()
        
    def update_subsidy_remaning(self):
        doc = frappe.get_doc("Loan", self.doc.against_loan)

        ld = frappe.qb.DocType("Loan Disbursement")

        subsidy_used = (
            frappe.qb.from_(ld).select(Sum(ld.subsidy_amount))
            .where((ld.against_loan == self.doc.against_loan) & (ld.docstatus == 1))
        ).run()[0][0] or 0

        if doc.loan_subsidy < subsidy_used:
            frappe.throw("Subsidy for Loan already exceeds")

        doc.db_set("total_subsidy_used", subsidy_used)

    def remove_subsidy_repayment(self):
        
        for lr in frappe.get_all("Loan Repayment", filters={"is_subsidy": 1, "loan_disbursement": self.doc.name}, pluck="name"):
            repayment = frappe.get_doc("Loan Repayment", lr)
            if repayment.docstatus == 1:
                repayment.cancel()

            repayment.delete()
