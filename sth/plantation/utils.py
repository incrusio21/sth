# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe

@frappe.whitelist()
def get_blok(divisi):
    filters = { "divisi": divisi }
    fields = ["name as item", "tahun_tanam", "luas_areal as vlm"]

    return frappe.get_all("Blok", filters=filters, fields=fields)

@frappe.whitelist()
def get_rate_item(item, company, doctype="Item"):
    rate = 0

    if doctype == "Item":
        rate = frappe.get_value("Item Price", {"item_code": item}, "price_list_rate")
    else:
        rate = frappe.get_value("Company Rate", {"parent": item, "company": company, "parenttype": doctype}, "rate") or 0

    return { "rate": rate }