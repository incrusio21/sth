# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import json

import frappe

@frappe.whitelist()
def get_blok(args):
    if isinstance(args, str):
        args = json.loads(args)
            
    fields = ["name as item", "tahun_tanam", "luas_areal", "sph", "jumlah_pokok"]

    return frappe.get_all("Blok", filters=args, fields=fields)

@frappe.whitelist()
def get_details_item(item, company, doctype="Item"):
    item_details = { "rate": 0, "accounts": "" }
    match doctype:
        case "Item":
            item_details["rate"] = frappe.get_value("Item Price", {"item_code": item}, "price_list_rate") 
        case "Data Kapital":
            item_details["rate"] = frappe.get_value("Data Kapital", item, "rate")
        case "Alat Berat Dan Kendaraan":
            item_details["rate"] = frappe.get_value("Alat Berat Dan Kendaraan", item, "basis_rpkg")
        case "Kegiatan":
            item_details["rate"] = frappe.get_value("Kegiatan", item, "rp_basis")
        case _:
            item_details = frappe.get_value("Company Rate", {"parent": item, "company": company, "parenttype": doctype}, ["rate", "account"], as_dict=1)

    return item_details