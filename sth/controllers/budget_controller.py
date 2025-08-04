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

    def validate(self):
        self.calculate_item_values()
        self.calculate_grand_total()

    def calculate_item_values(self):
        for df in self._get_table_fields():
            amount_total = 0.0
            for d in self.get(df.fieldname):
                d.amount = flt(d.rate * d.qty)
                self.calculate_sebaran_values(d)
                amount_total += d.amount

            self.set(f"{df.fieldname}_total", amount_total)
            
    def calculate_sebaran_values(self, item):
        total_sebaran = 0.0
        for month in MONTHS:
            item.set(f"rp_{month}", 
                flt(item.amount * (self.get(f"per_{month}") / 100))
            )

            total_sebaran += item.get(f"rp_{month}")

        if total_sebaran > item.amount:
            frappe.throw(_("Distribution exceeds 100%. Please recheck your input."))

    def calculate_grand_total(self):
        grand_total = 0.0
        for df in self._get_table_fields():
            grand_total += self.get(f"{df.fieldname}_total")

        self.grand_total = grand_total