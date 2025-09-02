# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.utils import flt, get_link_to_form
from frappe.desk.reportview import get_filters_cond, get_match_cond

from sth.controllers.plantation_controller import PlantationController

class RencanaKerjaController(PlantationController):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def validate(self):
        super().validate()

    
    def calculate_item_table_values(self):
        for df in self._get_table_fields():
            self.calculate_item_values(df.options, df.fieldname, ["budget_tambahan"])

        self.mandor_amount = flt(self.upah_mandor) + flt(self.premi_mandor)
        self.kerani_amount = flt(self.upah_kerani) + flt(self.premi_kerani)
        self.mandor1_amount = flt(self.upah_mandor1) + flt(self.premi_mandor1)

@frappe.whitelist()
def duplicate_rencana_kerja(voucher_type, voucher_no, blok, fieldname_addons=None):
    doc = frappe.get_doc(voucher_type, voucher_no)

    if isinstance(blok, str):
        blok = json.loads(blok)

    if fieldname_addons and isinstance(fieldname_addons, str):
        fieldname_addons = json.loads(fieldname_addons)

    new_doc_list = []
    for d in blok:
        new_doc = frappe.new_doc(voucher_type)
        new_doc.update(doc.as_dict(no_default_fields=True))
        new_doc.blok = d["item"]
        
        for key, fieldname in fieldname_addons.items():
            new_doc.set(fieldname, d.get(key))

        new_doc.submit()
        new_doc_list.append(get_link_to_form(voucher_type, new_doc.name))

    frappe.msgprint("List of {} generated from duplicates. <br> {}".format(voucher_type, "<br>".join(new_doc_list)))

@frappe.whitelist()
def get_not_used_blok(args):
    if isinstance(args, str):
        args = json.loads(args)

    conditions = []

    fieldname = ""
    if args.get("fieldname"):
        fieldname += ",`tabBlok`." + ",`tabBlok`.".join(args.get("fieldname"))
        
    # tolong d ubah klo ada waktu
    return frappe.db.sql("""
        SELECT `tabBlok`.name as item, `tabBlok`.tahun_tanam, `tabBlok`.luas_areal, `tabBlok`.sph, `tabBlok`.jumlah_pokok {fieldname}
        FROM `tabBlok`
        left join `tab{doctype}` on `tabBlok`.name = `tab{doctype}`.blok 
        WHERE `tab{doctype}`.docstatus != 1 or `tab{doctype}`.blok is null
        {fcond}{mcond}
    """.format(
        **{
            "fcond": get_filters_cond("Blok", args["filters"], conditions),
            "mcond": get_match_cond("Blok"),
            "doctype": args["doctype"],
            "fieldname": fieldname
        }
    ), as_dict=1
)