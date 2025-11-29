# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def update_task_progress(self, method):
    order_item, cond = [], ""   
    for item in self.items:
        cond += """ WHEN (purchase_order = {} and purchase_order_item = {}) THEN {}
            """.format(
            frappe.db.escape(self.name),
            frappe.db.escape(item.name),
            item.progress_received,
        )

        order_item.append(item.name)

    if order_item:
        frappe.db.sql(
            """ UPDATE `tabTask`
            SET
                progress = CASE {} END
            WHERE
                purchase_order_item in %(po_details)s """.format(cond),
            {"po_details": order_item}, debug=1
        )

@frappe.whitelist()
def get_kegiatan_item(kegiatan):
    keg_doc = frappe.get_cached_doc("Kegiatan", kegiatan)

    # memastikan terdapat item pada kegiatan
    if not keg_doc.item_code:
        frappe.throw(_("Please set Item Code for Kegiatan first"))

    return {
        "item_code": keg_doc.item_code,
        "uom": keg_doc.uom
    }