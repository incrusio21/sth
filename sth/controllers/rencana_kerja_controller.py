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


@frappe.whitelist()
def duplicate_rencana_kerja(voucher_type, voucher_no, blok):
    doc = frappe.get_doc(voucher_type, voucher_no)

    if isinstance(blok, str):
        blok = json.loads(blok)

    new_doc_list = []
    for d in blok:
        new_doc = frappe.new_doc(voucher_type)
        new_doc.update(doc.as_dict(no_default_fields=True))
        new_doc.blok = d

        new_doc.submit()
        new_doc_list.append(get_link_to_form(voucher_type, new_doc.name))

    frappe.msgprint("List of {} generated from duplicates. <br> {}".format(voucher_type, "<br>".join(new_doc_list)))

@frappe.whitelist()
def get_not_used_blok(args):
    if isinstance(args, str):
        args = json.loads(args)

    conditions = []

    fieldname = ""
    # tolong d ubah klo ada waktu
    return frappe.db.sql("""
        SELECT `tabBlok`.name as item, `tabBlok`.tahun_tanam, `tabBlok`.luas_areal, `tabBlok`.sph, `tabBlok`.jumlah_pokok {fieldname}
        FROM `tabBlok`
        left join `tab{doctype}` on `tabBlok`.name = `tab{doctype}`.blok 
        WHERE `tab{doctype}`.docstatus < 2 or `tab{doctype}`.blok is null
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