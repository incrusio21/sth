# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

from frappe.model.document import Document

MONTHS = [
    'januari', 'februari', 'maret', 'april', 'mei', 'juni',
    'juli', 'agustus', 'september', 'oktober', 'november', 'desember'
]

class BudgetController(Document):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.skip_table_amount = []

    def validate(self):
        self.calculate_item_table_values()
        self.calculate_grand_total()

    def calculate_item_table_values(self):
        for df in self._get_table_fields():
            
            self.calculate_item_values(df.options, df.fieldname)

    def calculate_item_values(self, options, table_fieldname):
        total = {"amount": 0, "qty": 0, "rotasi": 0}
        rotasi_total = 0
        table_item = self.get(table_fieldname)
        
        # set precision setiap table agar pembulatan untuk menghidari selesih grand total akibat floating-point precision
        precision = frappe.get_precision(options, "amount")

        # cari fieldname dengan kata rp pada table
        per_month_table = list(filter(lambda key: "rp_" in key, frappe.get_meta(options).get_valid_columns()))
        for d in table_item:
            d.amount = flt(d.rate * d.qty * (d.get("rotasi") or 1), precision)
            if per_month_table:
                self.calculate_sebaran_values(d, per_month_table)

            total["amount"] += d.amount
            total["qty"] += d.qty
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
        for df in self._get_table_fields():
            # skip perhitungan total untuk table tertentu
            if df.fieldname in self.skip_table_amount:
                continue

            grand_total += self.get(f"{df.fieldname}_amount")

        self.grand_total = grand_total