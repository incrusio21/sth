# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt

from frappe.model.document import Document

class PlantationController(Document):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.skip_table_amount = []
        self.skip_fieldname_amount = []

    def validate(self):
        self.calculate_item_table_values()
        self.calculate_grand_total()

    def calculate_item_table_values(self):
        for df in self._get_table_fields():
            self.calculate_item_values(df.options, df.fieldname)

    def calculate_item_values(self, options, table_fieldname, field_tambahan=[]):
        total = {"amount": 0, "qty": 0, "rotasi": 0}
        rotasi_total = 0
        table_item = self.get(table_fieldname)
        
        # set precision setiap table agar pembulatan untuk menghidari selesih grand total akibat floating-point precision
        precision = frappe.get_precision(options, "amount")

        # cari fieldname dengan kata rp pada table
        per_month_table = list(filter(lambda key: "rp_" in key, frappe.get_meta(options).get_valid_columns()))
        for d in table_item:
            d.amount = flt(d.rate * flt(d.qty) * (d.get("rotasi") or 1), precision)
            for fieldname in field_tambahan:
                d.amount += d.get(fieldname) or 0

            if per_month_table:
                self.calculate_sebaran_values(d, per_month_table)

            total["amount"] += d.amount
            total["qty"] += flt(d.qty)
            rotasi_total += d.get("rotasi") or 0

        total["rotasi"] = (rotasi_total / len(table_item) if table_item else 0)
        for total_field in ["amount", "qty", "rotasi"]:
            fieldname = f"{table_fieldname}_{total_field}"
            if not self.meta.has_field(fieldname):
                continue
            
            self.set(fieldname, flt(total[total_field], self.precision(fieldname)))

    def calculate_sebaran_values(self, item, sebaran_list=[]):
        # hitung nilai sebaran selama 12 bulan
        for sbr in sebaran_list:
            per_field = sbr.replace("rp_", "per_")

            # default 0 frappe selalu berbentuk string
            per_month = flt(self.get(per_field))
            item.set(sbr, 
                flt(item.amount * (per_month / 100), item.precision(sbr))
            )

    def calculate_grand_total(self):
        grand_total = 0.0
        amount_fieldname = list(filter(lambda key: "amount" in key, self.meta.get_valid_columns()))
        for fieldname in amount_fieldname:
            # skip perhitungan total untuk table/fieldname tertentu
            if fieldname.replace("_amount", "") in self.skip_table_amount \
                or fieldname in self.skip_fieldname_amount:
                continue

            grand_total += self.get(fieldname) or 0

        self.grand_total = grand_total