# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

def validate_progress_received(self, method):
    po_list = {}
    # get list po dan name itemny
    for item in self.items:
        if item.purchase_order and item.purchase_order_item:
            po_list.setdefault(item.purchase_order, []).append(item.purchase_order_item)

    for po_name, item_list in po_list.items():
        po = frappe.get_doc("Purchase Order", po_name, for_update=True)
        # run hanya untuk ambil key onload
        po.run_method("onload")

        # check apakah flow purchase type sesuai
        if po.get_onload("future_type") != self.purchase_type:
            frappe.throw(_(f"Purchase type mismatch: {self.purchase_type} cannot follow {po.purchase_type}"))

        # jika po bukan submit atau bukan merupakan check progress
        if po.docstatus != 1 or not po.get_onload("check_progress"):
            continue
        
        for po_item in po.items:
            if po_item.name not in item_list:
                continue

            # jika progress received lebih kecil dari persentasi received munculkan error
            if flt(po_item.progress_received) < flt(po_item.received_qty/po_item.qty*100):
                frappe.throw(_(f"Progress on {po.name} at Row#{po_item.idx} cannot exceed {po_item.progress_received}%"))