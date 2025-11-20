import frappe,json
from frappe.utils import now
from erpnext.buying.doctype.request_for_quotation.request_for_quotation import make_supplier_quotation_from_rfq
from erpnext.stock.get_item_details import get_item_details
from sth.utils import decrypt

@frappe.whitelist(allow_guest=True)
def create_sq():
    data = frappe.form_dict
    invalidMessage = validate_request(data)
    if invalidMessage: 
        frappe.local.response["http_status_code"] = 422
        return invalidMessage
    
    rfq_name = decrypt(data.get("rfq"))
    
    doc_sq = make_supplier_quotation_from_rfq(rfq_name,for_supplier=data.get("supplier"))
    doc_sq.custom_file_upload = f"/private/files/{data.file_url}"
    doc_sq.valid_till = doc_sq.transaction_date
    mq_ref = doc_sq.items[0].material_request
    doc_sq.items = []
    
    for item in json.loads(data.get("items")):
        item_details = get_item_details({"item_code":item["item_code"],"company": doc_sq.company,"doctype": doc_sq.doctype,"conversion_rate":doc_sq.conversion_rate})

        child  = doc_sq.append("items")
        child.update(item_details)
        child.description = item["desc"]
        child.rate = item["rate"]
        child.qty = item["qty"]
        child.material_request = mq_ref
        child.request_for_quotation = rfq_name
    doc_sq.insert()

    frappe.db.commit()
    return {
        "doctype": doc_sq.doctype,
        "docname": doc_sq.name,
    }

def validate_request(data):
    message = []
    if not data.get("rfq"):
        message.append("RFQ is required")
    
    if not data.get("supplier"):
        message.append("Supplier is required")
    
    if not json.loads(data.get("items")):
        message.append("Items is required")
    
    if not data.get("file_url"):
        message.append("File upload is required")
    
    return message