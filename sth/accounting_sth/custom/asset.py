import frappe
from frappe import _

def cek_prec_untuk_asset(doc, method):

    if not doc.purchase_receipt:
        return
    
    pr_item = frappe.db.get_value(
        "Purchase Receipt Item",
        doc.purchase_receipt_item,
        ["qty", "item_code", "parent"],
        as_dict=True
    )
    
    if not pr_item:
        frappe.throw(_("Purchase Receipt Item not found"))
    
    filters = {
        "purchase_receipt": doc.purchase_receipt,
        "purchase_receipt_item": doc.purchase_receipt_item,
        "docstatus": ["!=", 2]  # Exclude cancelled assets
    }
    
    if not doc.is_new():
        filters["name"] = ["!=", doc.name]
    
    existing_assets_count = frappe.db.count("Asset", filters)
    
    total_assets = existing_assets_count + 1
    
    if total_assets > pr_item.qty:
        frappe.throw(
            _("Cannot create asset. Total assets ({0}) from Purchase Receipt {1} (Item: {2}) exceeds available quantity ({3})").format(
                total_assets,
                doc.purchase_receipt,
                pr_item.item_code,
                pr_item.qty
            )
        )
    