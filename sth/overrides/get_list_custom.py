import frappe
import json

@frappe.whitelist()
def get_filtered_list(doctype, filters, fields, parent, limit_page_length, order_by):
    # Get excluded names
    if isinstance(filters, str):
        filters = json.loads(filters)

    excluded_names = frappe.db.sql("""
        SELECT material_request_item 
        FROM `tabRequest for Quotation Item` rqi 
        JOIN `tabRequest for Quotation` rfq ON rqi.parent = rfq.name  
        WHERE rfq.docstatus < 2
    """, as_dict=False)
    
    excluded_names = [name[0] for name in excluded_names if name[0]]
    
    # Build filters
    if excluded_names:
        filters.append(["name", "not in", excluded_names])
    
    return frappe.client.get_list(
        doctype=doctype,
        filters=filters,
        fields=fields,
        parent=parent,
        limit_page_length=limit_page_length,
        order_by=order_by
    )
