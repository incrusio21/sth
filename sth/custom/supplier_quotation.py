import frappe,json

@frappe.whitelist()
def close_rfq(rfq):
    frappe.db.set_value("Request for Quotation",rfq,"custom_offering_status","Closed",update_modified=False)


def create_po_draft(doc,method):
    from sth.overrides.supplier_quotation import make_purchase_order
    po = make_purchase_order(doc.name)
    po.insert()

@frappe.whitelist()
def close_status_another_sq(reference,except_name):
    supplier_quotations = frappe.db.sql("""
        select sq.name from `tabSupplier Quotation` sq
        join `tabSupplier Quotation Item` sqi on sqi.parent = sq.name
        where sq.workflow_state = "Open" and (sqi.request_for_quotation in %(reference)s or sq.custom_material_request in %(reference)s
        and sq.name not in %(except_name)s
        group by sq.name
    """,{"reference":reference,"except_name":except_name},as_dict=True)

    for row in supplier_quotations:
        frappe.db.set_value("Supplier Quotation",row.name,"workflow_state","Closed")

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
    

@frappe.whitelist()
def get_taxes_template(company):
    data = frappe.db.get_all("Procurement Settings Account",{"company": company},["company","account","type"])
    return data

@frappe.whitelist()
def get_account_tax_rate(name,company):
    return frappe.db.get_value("Tax Rate Account",{"parent":name,"company": company},["account"])