# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

def validate_progress_received(self, method):
    po_list = {}
    # harusny ada setingan
    if self.purchase_type != "BAPP":
        return
    
    # get list po dan name itemny
    for item in self.items:
        if item.proposal and item.proposal_item:
            po_list.setdefault(item.proposal, []).append(item.proposal_item)

    for po_name, item_list in po_list.items():
        po = frappe.get_doc("Proposal", po_name, for_update=True)

        # jika po bukan submit atau bukan merupakan check progress
        if po.docstatus != 1:
            continue
        
        for po_item in po.items:
            if po_item.name not in item_list:
                continue

            # jika progress received lebih kecil dari persentasi received munculkan error
            if flt(po_item.progress_received) < flt(po_item.received_qty):
                frappe.throw(_(f"Progress on {po.name} at Row#{po_item.idx} cannot exceed {po_item.progress_received}"))