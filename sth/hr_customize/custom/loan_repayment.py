# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe

class LoanRepayment:
    def __init__(self, doc, method):
        self.doc = doc
        self.method = method

        match self.method:
            case "on_cancel":
                self.validate_subsidy()

    def validate_subsidy(self):
        if self.doc.is_paid:
            frappe.throw("Payment for Repayment {} has been made".format(self.doc.name))

        if self.doc.is_subsidy and \
            frappe.get_value("Loan Disbursement", self.doc.loan_disbursement, "docstatus") == 1:

            frappe.throw("Document only can remove by cancel Loan Disbursement {}".format(self.doc.name))