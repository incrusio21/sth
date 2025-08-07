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
        self.calculate_item_values()
        self.calculate_grand_total()

    def calculate_item_values(self):
        for df in self._get_table_fields():
            total = {"amount": 0, "qty": 0, "rotasi": 0}
            rotasi_total = 0
            table_item = self.get(df.fieldname)
            # set precision setiap table agar pembulatan selalu sama
            precision = frappe.get_precision(df.options, "amount")
            for d in table_item:
                d.amount = flt(d.rate * d.qty * (d.get("rotasi") or 1), precision)
                self.calculate_sebaran_values(d)

                total["amount"] += d.amount
                total["qty"] += d.qty
                rotasi_total += d.get("rotasi") or 0

            total["rotasi"] = (rotasi_total / len(table_item) if table_item else 0)
            for total_field in ["amount", "qty", "rotasi"]:
                fieldname = f"{df.fieldname}_{total_field}"
                if not self.meta.has_field(fieldname):
                    continue
                
                self.set(fieldname, flt(total[total_field], self.precision(fieldname)))
            
    def calculate_sebaran_values(self, item):
        total_sebaran = 0.0
        # hitung nilai sebaran selama 12 bulan
        for month in MONTHS:
            per_field = f"per_{month}"
            amount_field = f"rp_{month}"

            # default 0 frappe selalu berbentuk string
            per_month = flt(self.get(per_field))
            item.set(amount_field, 
                flt(item.amount * (per_month / 100), item.precision(amount_field))
            )
            
            # pembanding dengan nilai amount jika melebihi 100%
            total_sebaran += item.get(amount_field)

        if total_sebaran > item.amount:
            frappe.throw(_("Distribution exceeds 100%. Please recheck your input."))

    def calculate_grand_total(self):
        grand_total = 0.0
        for df in self._get_table_fields():
            # skip perhitungan total untuk table tertentu
            if df.fieldname in self.skip_table_amount:
                continue

            grand_total += self.get(f"{df.fieldname}_amount")

        self.grand_total = grand_total