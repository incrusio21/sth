# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from cryptography.fernet import Fernet
from sth.utils import decrypt

no_cache = True

def get_context(context):
    csrf_token = frappe.sessions.get_csrf_token()
    params = frappe.form_dict
    supplier = params.get("supp") or ""
    rfqEn = params.get("name") or ""
    rfq_name = decrypt(rfqEn)
    context.rfq = rfqEn
    context.supplier = decrypt(supplier)
    context["csrf_token"] = csrf_token

    doc = frappe.get_doc("Request for Quotation",rfq_name)
    doc_dict = doc.as_dict()
    context.items = doc.get("items")
    context.status = doc.get("custom_offering_status")    

    return context



