# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class EmployeePaymentLog(Document):
    
    def validate(self):
        self.document_already_paid()

    def on_trash(self):
        self.document_already_paid()

    def document_already_paid(self):
        if self.is_paid:
            frappe.throw("Payment for Employee {} has been made.".format(self.employee))