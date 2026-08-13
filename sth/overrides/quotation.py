import frappe
from erpnext.selling.doctype.quotation.quotation import _make_sales_order as original_make_sales_order

@frappe.whitelist()
def make_sales_order(source_name, target_doc=None, ignore_permissions=False):
    doclist = original_make_sales_order(source_name, target_doc, ignore_permissions)

    quotation_date = frappe.db.get_value("Quotation", source_name, "transaction_date")
    if quotation_date:
        doclist.transaction_date = quotation_date

    return doclist