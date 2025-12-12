# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class EmployeePaymentLog(Document):
    
    def validate(self):
        self.set_status()
        self.document_already_paid()

    def set_status(self):
        if not self.status:
            self.status = "Approved"

    def on_trash(self):
        # self.remove_document()
        self.document_already_paid()
    
    def remove_document(self):
        # skip jika berasal dari transaksi
        if self.flags.transaction_employee:
            return
        
        msg = _("Individual Employee Payment Ledger Entry cannot be deleted.")
        msg += "<br>" + _("Please cancel related transaction.")
        frappe.throw(msg)

    def document_already_paid(self):
        if self.is_paid:
            frappe.throw("Payment for Employee {} has been made.".format(self.employee))