# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.utils import flt, get_link_to_form
from frappe.desk.reportview import get_filters_cond, get_match_cond
from frappe.query_builder.functions import Coalesce, Sum

from sth.controllers.plantation_controller import PlantationController

class RencanaKerjaController(PlantationController):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.skip_calculate_supervisi = False
        self.realization_doctype = ""

    def validate(self):
        if not self.skip_calculate_supervisi:
            self.calculate_supervisi_amount()

        super().validate()
        self.calculate_biaya_kerja_total()

    def calculate_supervisi_amount(self):
        self.mandor_amount = flt((self.upah_mandor or 0) + (self.premi_mandor or 0))
        self.kerani_amount = flt((self.upah_kerani or 0) + (self.premi_kerani or 0))
        self.mandor1_amount = flt((self.upah_mandor1 or 0) + (self.premi_mandor1 or 0))

    def calculate_biaya_kerja_total(self):
        self.biaya_kerja_total = self.grand_total
        
        if not self.skip_calculate_supervisi:
           self.biaya_kerja_total -= self.mandor_amount - self.kerani_amount - self.mandor1_amount

        self.realized_total = self.used_total = 0.0

    def update_value_after_amount(self, item, precision):
        # set on child class if needed
        item.amount = flt(item.amount + (item.get("budget_tambahan") or 0), precision)

    def calculate_used_and_realized(self):
        rkh = frappe.qb.DocType("Rencana Kerja Harian")

        self.used_total = (
			frappe.qb.from_(rkh)
			.select(
				Sum(rkh.grand_total)
            )
			.where(
                (rkh.docstatus == 1) &
                (rkh.voucher_type == self.doctype) &
                (rkh.voucher_no == self.name)
			)
		).run()[0][0] or 0.0

        if self.used_total > self.biaya_kerja_total:
            frappe.throw("Used Total exceeds limit.")

        if self.realization_doctype:
            bkm = frappe.qb.DocType(self.realization_doctype)

            self.realized_total, self.realized_tenaga_kerja = (
                frappe.qb.from_(bkm)
                .select(
                    Coalesce(Sum(bkm.grand_total), 0), 
                    Coalesce(Sum(bkm.hari_kerja_total), 0)
                )
                .where(
                    (bkm.docstatus == 1) &
                    (bkm.voucher_type == self.doctype) &
                    (bkm.voucher_no == self.name)
                )
            ).run()[0]
            
            if self.realized_total > self.biaya_kerja_total:
                frappe.throw("Realization Total exceeds limit.")

            if self.realized_tenaga_kerja > self.jumlah_tenaga_kerja:
                frappe.throw("Realization Hari Kerja exceeds Jumlah Hari Kerja.")
        
        self.db_update()

@frappe.whitelist()
def duplicate_rencana_kerja(voucher_type, voucher_no, blok, is_batch=None, fieldname_addons=None):
    doc = frappe.get_doc(voucher_type, voucher_no)

    if isinstance(blok, str):
        blok = json.loads(blok)

    if fieldname_addons and isinstance(fieldname_addons, str):
        fieldname_addons = json.loads(fieldname_addons)

    new_doc_list = []
    for d in blok:
        new_doc = frappe.new_doc(voucher_type)
        new_doc.update(doc.as_dict(no_default_fields=True))
        if is_batch:
            new_doc.batch = d["item"]
        else:    
            new_doc.blok = d["item"]

        for key, fieldname in (fieldname_addons or {}).items():
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