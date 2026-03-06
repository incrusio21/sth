# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class TBSGabunganSetting(Document):

    def validate(self):
        self.validate_duplicate_unit_supplier()

    def validate_duplicate_unit_supplier(self):

        if self.all_supplier:

            existing = frappe.db.sql("""
                SELECT name
                FROM `tabTBS Gabungan Setting`
                WHERE unit = %s
                AND name != %s
                LIMIT 1
            """, (self.unit, self.name), as_dict=True)

            if existing:
                docname = existing[0].name
                frappe.throw(
                    f"Unit <b>{self.unit}</b> sudah memiliki setting di dokumen "
                    f"<a href='/app/tbs-gabungan-setting/{docname}'>{docname}</a>. "
                    f"Tidak bisa membuat All Supplier."
                )

        else:

            existing_all = frappe.db.sql("""
                SELECT name
                FROM `tabTBS Gabungan Setting`
                WHERE unit = %s
                AND all_supplier = 1
                AND name != %s
                LIMIT 1
            """, (self.unit, self.name), as_dict=True)

            if existing_all:
                docname = existing_all[0].name
                frappe.throw(
                    f"Unit <b>{self.unit}</b> sudah menggunakan All Supplier "
                    f"di dokumen "
                    f"<a href='/app/tbs-gabungan-setting/{docname}'>{docname}</a>."
                )

        if not self.all_supplier:

            for row in self.tbs_gabungan_supplier:

                if not row.supplier:
                    continue

                existing_supplier = frappe.db.sql("""
                    SELECT g.name
                    FROM `tabTBS Gabungan Setting` g
                    JOIN `tabTBS Gabungan Supplier` s ON s.parent = g.name
                    WHERE g.unit = %s
                    AND s.supplier = %s
                    AND g.name != %s
                    LIMIT 1
                """, (
                    self.unit,
                    row.supplier,
                    self.name
                ), as_dict=True)

                if existing_supplier:
                    docname = existing_supplier[0].name

                    frappe.throw(
                        f"Kombinasi Unit <b>{self.unit}</b>, "
                        f"Supplier <b>{row.supplier}</b> "
                        f"sudah ada di dokumen "
                        f"<a href='/app/tbs-gabungan-setting/{docname}'>{docname}</a>."
                    )