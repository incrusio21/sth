# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt, get_link_to_form
from frappe.model.workflow import get_workflow_name, is_transition_condition_satisfied

def onload_order_type(self, method):
    if not self.purchase_type:
        return
    
    order_type = frappe.get_cached_doc("Purchase Type", self.purchase_type)

    self._purchase_type_field = ["future_type", "check_progress", "progress_benchmark"]
    self.run_method("field_purchase_type")
    # check apakah po butuh check progress dan apa field apa yg d gunakan untuk penamaan (items_code, kegiatan)
    for d in self._purchase_type_field:
        self.set_onload(d, order_type.get(d))

@frappe.whitelist()
def update_progress_item(parent_doctype, trans_items, parent_doctype_name, child_docname="items"):
    def check_doc_permissions(doc, perm_type="create"):
        try:
            doc.check_permission(perm_type)
        except frappe.PermissionError:
            actions = {"create": "add", "write": "update"}

            frappe.throw(
                _("You do not have permissions to {} items in a {}.").format(
                    actions[perm_type], parent_doctype
                ),
                title=_("Insufficient Permissions"),
            )

    def validate_workflow_conditions(doc):
        workflow = get_workflow_name(doc.doctype)
        if not workflow:
            return

        workflow_doc = frappe.get_doc("Workflow", workflow)
        current_state = doc.get(workflow_doc.workflow_state_field)
        roles = frappe.get_roles()

        transitions = []
        for transition in workflow_doc.transitions:
            if transition.next_state == current_state and transition.allowed in roles:
                if not is_transition_condition_satisfied(transition, doc):
                    continue
                transitions.append(transition.as_dict())

        if not transitions:
            frappe.throw(
                _("You are not allowed to update as per the conditions set in {} Workflow.").format(
                    get_link_to_form("Workflow", workflow)
                ),
                title=_("Insufficient Permissions"),
            )

    def validate_progress(child_item, new_data):
        if flt(new_data.get("progress_received")) < flt(child_item.received_qt):
            frappe.throw(_("Cannot set Progress less than received quantity"))

    data = json.loads(trans_items)
    any_update = False
    parent = frappe.get_doc(parent_doctype, parent_doctype_name)
    check_doc_permissions(parent, "write")

    for d in data:
        check_doc_permissions(parent, "write")
        child_item = parent.get(child_docname, {"name": d.get("docname")})[0]

        prev_progress_received, new_progress_received = flt(child_item.get("progress_received")), flt(d.get("progress_received"))

        progress_received_unchanged = prev_progress_received == new_progress_received
        if (
            progress_received_unchanged
        ):
            continue

        validate_progress(child_item, d)

        child_item.progress_received = flt(d.get("progress_received"))

        any_update = True
    
    if any_update:
        parent.flags.ignore_validate_update_after_submit = True
        parent.save()
    
    parent.reload()
    validate_workflow_conditions(parent)
    
@frappe.whitelist()
def make_purchase_receipt(source_name, target_doc=None):
    has_unit_price_items, purchase_type = frappe.db.get_value("Purchase Order", source_name, ["has_unit_price_items", "purchase_type"])

    def set_missing_values(source, target):
        target.purchase_type = frappe.get_value("Purchase Type", source.purchase_type, "future_type")

        target.run_method("set_missing_values")
        target.run_method("calculate_taxes_and_totals")
        
    def is_unit_price_row(source):
        return has_unit_price_items and source.qty == 0

    def max_qty(source):
        max_qty = source.qty
        if purchase_type in ("Borongan", "Capex"):
            max_qty = source.progress_received
            
        return max_qty
    
    def update_item(obj, target, source_parent):
        qty = max_qty(obj)

        target.qty = flt(obj.qty) if is_unit_price_row(obj) else flt(qty) - flt(obj.received_qty)
        target.stock_qty = (flt(qty) - flt(obj.received_qty)) * flt(obj.conversion_factor)
        target.amount = (flt(qty) - flt(obj.received_qty)) * flt(obj.rate)
        target.base_amount = (
            (flt(qty) - flt(obj.received_qty)) * flt(obj.rate) * flt(source_parent.conversion_rate)
        )

    doc = get_mapped_doc(
        "Purchase Order",
        source_name,
        {
            "Purchase Order": {
                "doctype": "Purchase Receipt",
                "field_map": {"supplier_warehouse": "supplier_warehouse"},
                "validation": {
                    "docstatus": ["=", 1],
                },
            },
            "Purchase Order Item": {
                "doctype": "Purchase Receipt Item",
                "field_map": {
                    "name": "purchase_order_item",
                    "parent": "purchase_order",
                    "bom": "bom",
                    "material_request": "material_request",
                    "material_request_item": "material_request_item",
                    "sales_order": "sales_order",
                    "sales_order_item": "sales_order_item",
                    "wip_composite_asset": "wip_composite_asset",
                },
                "postprocess": update_item,
                "condition": lambda doc: (
                    True if is_unit_price_row(doc) else abs(doc.received_qty) < abs(max_qty(doc))
                )
                and doc.delivered_by_supplier != 1,
            },
            "Purchase Taxes and Charges": {"doctype": "Purchase Taxes and Charges", "reset_value": True},
        },
        target_doc,
        set_missing_values,
    )

    return doc