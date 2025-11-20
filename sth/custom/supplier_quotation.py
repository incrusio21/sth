import frappe

def update_status_rfq(doc,method):
    rfq = doc.items[0].request_for_quotation
    if rfq:
        close_status_another_sq(rfq,doc.name)
        frappe.db.set_value("Request for Quotation",rfq,"custom_offering_status","Closed",update_modified=False)
        frappe.db.commit()

def close_status_another_sq(rfq,except_name):
    supplier_quotations = frappe.db.sql("""
        select sq.name from `tabSupplier Quotation` sq
        join `tabSupplier Quotation Item` sqi on sqi.parent = sq.name
        where sq.workflow_state = "Open" and sqi.request_for_quotation = %s 
        and sq.name <> %s
        group by sq.name
    """,[rfq,except_name],as_dict=True)

    for row in supplier_quotations:
        frappe.db.set_value("Supplier Quotation",row.name,"workflow_state","Closed")
        frappe.db.commit()

@frappe.whitelist()
def reopen_rfq(name):
    frappe.db.set_value("Request for Quotation",name,{
        "custom_offering_status":"Open"
    },update_modified=False)
    frappe.db.commit()

    supplier_quotations = frappe.db.sql("""
        select sq.name from `tabSupplier Quotation` sq
        join `tabSupplier Quotation Item` sqi on sqi.parent = sq.name
        where sq.workflow_state in ("Closed","Approved") and sqi.request_for_quotation = %s 
        group by sq.name
    """,[name],as_dict=True)

    for row in supplier_quotations:
        frappe.db.set_value("Supplier Quotation",row.name,{
            "workflow_state":"Open",
            "docstatus": 0
        },update_modified=False)
        frappe.db.commit()