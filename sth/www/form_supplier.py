# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from cryptography.fernet import Fernet
from sth.utils import decrypt

no_cache = True

def get_context(context):
    csrf_token = frappe.sessions.get_csrf_token()
    context["csrf_token"] = csrf_token
    params = frappe.form_dict
    payment_terms = [
        "7 hari setelah barang dan invoice diterima (Credit)",
        "14 hari setelah barang dan invoice diterima (Credit)",
        "30 hari setelah barang dan invoice diterima (Credit)",
        "45 hari setelah barang dan invoice diterima (Credit)",
        "60 hari setelah barang dan invoice diterima (Credit)",
        "90 hari setelah barang dan invoice diterima (Credit)",
        "120 hari setelah barang dan invoice diterima (Credit)",
        "CASH (CASH)",
        "Panjar / Down Payment (CASH)"
    ]

    if params.get("supp") and params.get("name"):
        supplier = params.get("supp") or ""
        rfqEn = params.get("name") or ""
        rfq_name = decrypt(rfqEn)
        context.rfq = rfqEn
        context.supplier = decrypt(supplier)
        
        doc = frappe.get_doc("Request for Quotation",rfq_name)
        context.items = doc.get("items")
        context.status = doc.get("custom_offering_status")
        context.country = frappe.get_all("Country",pluck="name")
        context.is_exist_sq = frappe.db.exists("Supplier Quotation Item",{"request_for_quotation": rfq_name})
        context.required_date = doc.schedule_date
        context.payment_terms = payment_terms
    return context



