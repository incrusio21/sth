# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, get_link_to_form

from sth.controllers.plantation_controller import PlantationController

class BudgetController(PlantationController):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.duplicate_param = ["budget_kebun_tahunan"]

    def validate(self):
        self.check_duplicate_data()
        super().validate()

        self.check_total_sebaran()
        self.calculate_item_sebaran_and_rotasi()

    def check_duplicate_data(self):
        if not self.duplicate_param:
            return
        
        filters = {"docstatus": 1, "name": ["!=", self.name]}
        for param in self.duplicate_param:
            filters[param] = self.get(param)

        if doc := frappe.db.get_value(self.doctype, filters):
            frappe.throw("{} is already use in <b>{}</b>".format(self.doctype, get_link_to_form(self.doctype, doc)))

    def update_value_after_amount(self, item, precision):
        # set on child class if needed
        item.amount = flt(item.amount * (item.get("rotasi") or 1), precision)

    def calculate_item_sebaran_and_rotasi(self):
        for df in self._get_table_fields():        
            rotasi_total = 0
            table_item = self.get(df.fieldname)

            # cari fieldname dengan kata rp pada table
            per_month_table = list(filter(lambda key: "rp_" in key, frappe.get_meta(df.options).get_valid_columns()))
            for d in table_item:
                rotasi_total += d.get("rotasi") or 0

                if per_month_table:
                    self.calculate_sebaran_values(d, per_month_table)

            # check jika ada rotasi untuk input total rotasi
            fieldname = f"{df.fieldname}_rotasi"
            if not self.meta.has_field(fieldname):
                continue

            self.set(fieldname, flt((rotasi_total / len(table_item)) if table_item else 0, self.precision(fieldname)))

    def calculate_sebaran_values(self, item, sebaran_list=[]):
        # hitung nilai sebaran selama 12 bulan
        for sbr in sebaran_list:
            per_field = sbr.replace("rp_", "per_")

            # default 0 frappe selalu berbentuk string
            per_month = flt(self.get(per_field))
            item.set(sbr, 
                flt(item.amount * (per_month / 100), item.precision(sbr))
            )

    def check_total_sebaran(self):
        total_sebaran = 0.0
        per_month_field = list(filter(lambda key: key.startswith("per_"), self.meta.get_valid_columns()))
        if not per_month_field:
            return 
            
        for month in per_month_field:
            if self.is_distibute:
                self.set(month, 100 / 12)

            total_sebaran += self.get(month)

        self.total_sebaran = flt(total_sebaran, self.precision("total_sebaran"))
        if self.total_sebaran != 100:
            frappe.throw(_(f"Total distribution is {'below' if self.total_sebaran < 100 else 'over'} 100%."))

    