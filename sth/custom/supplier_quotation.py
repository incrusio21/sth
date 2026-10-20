import frappe,json

def create_po_draft(doc,method):
    from sth.overrides.supplier_quotation import make_purchase_order
    po = make_purchase_order(doc.name)
    po.insert(ignore_mandatory=True)

def validate_duplicate_supplier(doc,method=None):
    material_requests = [ d.material_request for d in doc.items ]
    if not material_requests or doc.from_comparasion: return

    args = {
        "pr_sr": material_requests,
        "supplier": doc.supplier,
        "name": doc.name,
        "company": doc.company
    }

    exists = frappe.db.sql("""
        select sq.name from `tabSupplier Quotation` sq
        join `tabSupplier Quotation Item` sqi on sq.name = sqi.parent
        where 
            sqi.material_request in %(pr_sr)s 
            and sq.supplier = %(supplier)s 
            and sq.company = %(company)s
            and sq.name <> %(name)s 
            and sq.docstatus = 0 
            and sq.from_comparasion = 0
        group by sq.name
    """,args,as_dict=True)

    name = [ r.name for r in exists ]

    if exists:
        frappe.throw("Quotation dengan supplier {0} sudah ada: {1}".format(doc.supplier_name, ",".join(name)))


@frappe.whitelist()
def close_rfq(rfq):
    frappe.db.set_value("Request for Quotation",rfq,"custom_offering_status","Closed",update_modified=False)

@frappe.whitelist()
def close_status_another_sq(reference,except_name):
    supplier_quotations = frappe.db.sql("""
        select sq.name from `tabSupplier Quotation` sq
        join `tabSupplier Quotation Item` sqi on sqi.parent = sq.name
        where sq.workflow_state = "Need To Compare" and (sqi.request_for_quotation in %(reference)s or sq.custom_material_request in %(reference)s)
        and sq.name not in %(except_name)s
        group by sq.name
    """,{"reference":reference,"except_name":except_name},as_dict=True)

    for row in supplier_quotations:
        frappe.db.set_value("Supplier Quotation",row.name,"workflow_state","Closed")

def reopen_status_another_sq(pr_sr):
    supplier_quotations = frappe.db.sql("""
        select sq.name from `tabSupplier Quotation` sq
        join `tabSupplier Quotation Item` sqi on sqi.parent = sq.name
        where sq.workflow_state = "Closed" and sq.custom_material_request = %(pr_sr)s
        group by sq.name
    """,{"pr_sr":pr_sr},as_dict=True)

    for row in supplier_quotations:
            frappe.db.set_value("Supplier Quotation",row.name,"workflow_state","Need To Compare")


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
def get_account_tax_rate(name,company,tipe="Masukan"):
    return frappe.db.get_value("Tax Rate Account",{"parent":name,"company": company,"tipe":tipe},["account"])