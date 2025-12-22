# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt

class PurchaseOrder:
    def __init__(self, doc, method):
        self.doc = doc
        self.method = method

        match self.method:
            case "validate":
                self.validate_with_previous_doc()
            case "on_submit":
                self.update_previous_order()
            case "on_cancel":
                self.update_previous_order(cancel=1)
                    
    def validate_with_previous_doc(self):
        if not self.doc.from_order:
            return
        
        self.doc.compare_values(
            {"Purchase Order": [self.doc.from_order]}, 
            [["supplier", "="], ["company", "="], ["currency", "="], ["need_project", "="]]
        )
        for d in self.doc.items:
            self.doc.compare_values(
                {"Purchase Order Item": [d.from_order_item]}, 
                [
                    ["project", "="],
                    ["item_code", "="],
                    ["uom", "="],
                    ["conversion_factor", "="],
                ] , 
                d
            )
        
    def update_previous_order(self, cancel=0):
        if not self.doc.from_order:
            return
        
        if not cancel and frappe.db.exists(
            "Purchase Order", 
            {"name": ["!=", self.doc.name], "from_order": self.doc.from_order, "docstatus": 1
        }):
            frappe.throw("Purchase Order already have Revisions")
            
        prev_doc = frappe.get_doc("Purchase Order", self.doc.from_order)
        status = "Closed" if not cancel else "Draft"
        if prev_doc.docstatus == 1:
            prev_doc.update_status(status)
            prev_doc.update_blanket_order() 

def field_purchase_type(self, method):
    self._purchase_type_field.extend(["order_revisions"])

def update_task_progress(self, method):
    order_item, cond = [], ""   
    for item in self.items:
        cond += """ WHEN (purchase_order = {} and purchase_order_item = {}) THEN {}
            """.format(
            frappe.db.escape(self.name),
            frappe.db.escape(item.name),
            flt(item.progress_received/item.qty*100),
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

@frappe.whitelist()
def make_purchase_order_revision(source_name, target_doc=None):
    has_unit_price_items = frappe.db.get_value("Purchase Order", source_name, "has_unit_price_items")

    def set_missing_values(source, target):
        # pastikan po lama sudah memiliki project
        if source.need_project and not frappe.db.exists("Project", {"purchase_order": source.name}):
            frappe.throw("Please create a Project for the Purchase Order before making revisions")
        
        target.run_method("set_missing_values")
        target.run_method("calculate_taxes_and_totals")
        
    def is_unit_price_row(source):
        return has_unit_price_items and source.qty == 0

    def update_item(obj, target, source_parent):
        target.qty = flt(obj.qty) if is_unit_price_row(obj) else flt(obj.qty) - flt(obj.received_qty)
        target.stock_qty = (flt(obj.qty) - flt(obj.received_qty)) * flt(obj.conversion_factor)
        target.amount = (flt(obj.qty) - flt(obj.received_qty)) * flt(obj.rate)
        target.base_amount = (
            (flt(obj.qty) - flt(obj.received_qty)) * flt(obj.rate) * flt(source_parent.conversion_rate)
        )

    doc = get_mapped_doc(
        "Purchase Order",
        source_name,
        {
            "Purchase Order": {
                "doctype": "Purchase Order",
                "field_map": {
                    "supplier_warehouse": "supplier_warehouse",
                    "name": "from_order"
                },
                "validation": {
                    "docstatus": ["=", 1],
                },
            },
            "Purchase Order Item": {
                "doctype": "Purchase Order Item",
                "field_map": {
                    "name": "from_order_item",
                    "material_request": "material_request",
                    "material_request_item": "material_request_item",
                    "sales_order": "sales_order",
                    "sales_order_item": "sales_order_item",
                    "wip_composite_asset": "wip_composite_asset",
                },
                "postprocess": update_item,
                "condition": lambda doc: (
                    True if is_unit_price_row(doc) else abs(doc.received_qty) < abs(doc.qty)
                )
                and doc.delivered_by_supplier != 1,
            },
            "Purchase Taxes and Charges": {"doctype": "Purchase Taxes and Charges", "reset_value": True},
        },
        target_doc,
        set_missing_values,
    )

    return doc