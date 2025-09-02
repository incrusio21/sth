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

    def calculate_item_values(self, options, table_fieldname):
        total = {"amount": 0, "qty": 0, "rotasi": 0}
        rotasi_total = 0
        table_item = self.get(table_fieldname)
        
        # set precision setiap table agar pembulatan untuk menghidari selesih grand total akibat floating-point precision
        precision = frappe.get_precision(options, "amount")

        for d in table_item:
            # update nilai rate atau qty sebelum perhitungan
            self.update_rate_or_qty_value(d, precision)

            d.amount = flt(d.rate * flt(d.qty), precision)

            # update nilai setelah menghitung amount
            self.update_value_after_amount(d, precision)

            total["amount"] += d.amount
            total["qty"] += flt(d.qty)
            rotasi_total += d.get("rotasi") or 0

        total["rotasi"] = (rotasi_total / len(table_item) if table_item else 0)
        for total_field in ["amount", "qty", "rotasi"]:
            fieldname = f"{table_fieldname}_{total_field}"
            if not self.meta.has_field(fieldname):
                continue
            
            self.set(fieldname, flt(total[total_field], self.precision(fieldname)))

    def update_rate_or_qty_value(self, item, precision):
        # set on child class if needed
        pass

    def update_value_after_amount(self, item, precision):
        # set on child class if needed
        pass

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