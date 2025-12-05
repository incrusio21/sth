# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt

from sth.controllers.accounts_controller import AccountsController

class PlantationController(AccountsController):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_qty_fieldname = {}
        self.fieldname_total = ["amount"]
        self.skip_table_amount = []
        self.skip_calculate_table = []
        self.skip_fieldname_amount = ["outstanding_amount"]
        self.kegiatan_fetch_fieldname = ["uom"]
        self.kegiatan_fetch_if_empty_fieldname = []

    def validate(self):
        self.fetch_kegiatan_data()
        self.calculate()
        super().validate()

    def fetch_kegiatan_data(self):
        if not (self.kegiatan_fetch_fieldname or self.kegiatan_fetch_if_empty_fieldname):
            return
        
        if not (self.kegiatan and self.company):
            self.update({key: "" for key in self.kegiatan_fetch_fieldname})
        else:
            from sth.controllers.queries import kegiatan_fetch_data
            
            for fieldname in self.kegiatan_fetch_if_empty_fieldname:
                if self.get(fieldname) is None:
                    self.kegiatan_fetch_fieldname.append(fieldname)

            if self.kegiatan_fetch_fieldname:
                self.update(kegiatan_fetch_data(self.kegiatan, self.company, self.kegiatan_fetch_fieldname))

    def calculate(self):
        self.calculate_item_table_values()
        self.calculate_grand_total()

    def calculate_item_table_values(self):
        for df in self._get_table_fields():
            if df.fieldname in self.skip_calculate_table:
                continue

            self.calculate_item_values(df.options, df.fieldname)

    def calculate_item_values(self, options, table_fieldname):
        total = { f: 0 for f in self.fieldname_total}
        table_item = self.get(table_fieldname)
        
        # set precision setiap table agar pembulatan untuk menghidari selesih grand total akibat floating-point precision
        precision = frappe.get_precision(options, "amount")
        max_qty = self.max_qty_fieldname.get(table_fieldname)

        for d in table_item:
            # update nilai rate atau qty sebelum perhitungan
            self.update_rate_or_qty_value(d, precision)

            qty = self.get(max_qty)  if max_qty and d.qty > self.get(max_qty) else d.qty
            d.amount = flt((d.rate or 0) * qty, precision)

            # update nilai setelah menghitung amount
            self.update_value_after_amount(d, precision)

            for f in self.fieldname_total:
                if d.get(f):
                    total[f] += d.get(f)

        for total_field in self.fieldname_total:
            fieldname = f"{table_fieldname}_{total_field}"
            if not self.meta.has_field(fieldname):
                continue
            
            self.set(fieldname, flt(total[total_field], self.precision(fieldname)))

        self.after_calculate_item_values(table_fieldname, options, total)

    def update_rate_or_qty_value(self, item, precision):
        # set on child class if needed
        pass

    def update_value_after_amount(self, item, precision):
        # set on child class if needed
        pass
    
    def after_calculate_item_values(self, table_fieldname, options, total):
        # set on child class if needed
        pass

    def calculate_grand_total(self):
        grand_total = 0.0

        self.before_calculate_grand_total()

        amount_fieldname = list(filter(lambda key: "amount" in key, self.meta.get_valid_columns()))
        for fieldname in amount_fieldname:
            # skip perhitungan total untuk table/fieldname tertentu
            if fieldname.replace("_amount", "") in self.skip_table_amount \
                or fieldname in self.skip_fieldname_amount:
                continue

            grand_total += self.get(fieldname) or 0

        self.grand_total = grand_total

        self.after_calculate_grand_total()

    def before_calculate_grand_total(self):
        # set on child class if needed
        pass

    def after_calculate_grand_total(self):
        # set on child class if needed
        pass