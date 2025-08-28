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
        self.check_total_sebaran()
        super().validate()

    def check_duplicate_data(self):
        if not self.duplicate_param:
            return
        
        filters = {"docstatus": 1, "name": ["!=", self.name]}
        for param in self.duplicate_param:
            filters[param] = self.get(param)

        if doc := frappe.db.get_value(self.doctype, filters):
            frappe.throw("{} is already use in <b>{}</b>".format(self.doctype, get_link_to_form(self.doctype, doc)))

    def check_total_sebaran(self):
        per_month_field = list(filter(lambda key: key.startswith("per_"), self.meta.get_valid_columns()))
        total_sebaran = 0.0

        for month in per_month_field:
            total_sebaran += self.get(month)

        if total_sebaran != 100:
            frappe.throw(_(f"Total distribution is {'below' if total_sebaran < 100 else 'over'} 100%."))

    