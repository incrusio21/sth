# Copyright (c) 2026 DAS and Contributors
# License: GNU General Public License v3. See license.txt
import frappe

@frappe.whitelist()
def get_proposal_termin(proposal):
    return frappe.get_all("Payment Schedule", 
        filters={"parent": proposal, "term_used": 0}, 
        fields=["name as value", "payment_term as label"],
        order_by="idx"
    )