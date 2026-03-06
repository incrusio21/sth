# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe

def make_entry(self, method=None):
    if self.payment_type not in ("Pay"):
        return

    mkcm = frappe.new_doc("Mandiri Kopra Cash Management")
    mkcm.posting_date = self.request_release_date
    mkcm.company = self.company
    mkcm.status = "In Progress"
    mkcm.public_key = ""
    mkcm.path =  ""

    mkcm.flags.ignore_permissions = 1
    mkcm.flags.notify_update = False
    mkcm.submit()