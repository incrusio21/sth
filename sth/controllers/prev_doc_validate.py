# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe

from frappe.utils import get_link_to_form
from frappe.model.document import Document

class validate_previous_document:
    def __init__(self, doc: Document):
        self.doc = doc
        self.check_material()

    # pengecekan link ke rencana kerja bulanan perawatan material
    def check_material(self):
        if not self.doc.get("material"):
            return
        
        material_list = [m.item for m in self.doc.material]
        
        if not material_list:
            return
        
        rkb_m = frappe.qb.DocType("Detail Material RK")
        material_used = frappe._dict(
            (
                frappe.qb.from_(rkb_m)
                .select(
                    rkb_m.item, rkb_m.name
                )
                .where(
                    (rkb_m.item.isin(material_list)) &
                    (rkb_m.parent == self.doc.voucher_no)
                )
                .groupby(rkb_m.item)
            ).run()
        )

        for d in self.doc.material:
            rkb_material = material_used.get(d.item) or ""
            if not rkb_material:
                frappe.throw("Item {} is not listed in the {}.".format(d.item, get_link_to_form(self.doc.voucher_type, self.doc.voucher_no)))

            d.prevdoc_detail = rkb_material