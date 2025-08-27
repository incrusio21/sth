# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class PlantationController(Document):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.skip_table_amount = []
        self.skip_fieldname_amount = []

    def calculate_grand_total(self):
        grand_total = 0.0
        amount_fieldname = list(filter(lambda key: "_amount" in key, self.meta.get_valid_columns()))
        for fieldname in amount_fieldname:
            # skip perhitungan total untuk table/fieldname tertentu
            if fieldname.replace("_amount", "") in self.skip_table_amount \
                or fieldname in self.skip_fieldname_amount:
                continue

            grand_total += self.get(fieldname)

        self.grand_total = grand_total