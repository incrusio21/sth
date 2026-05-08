# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ReportKomersialdanFiskal(Document):
	pass


@frappe.whitelist()
def get_fiscal_assets(company):
    """
    Ambil semua asset sesuai filter yang sama dengan set_asset_filter di JS.
    Sekaligus JOIN ke finance_books (idx=1) agar tidak perlu N query terpisah.
    """
    assets = frappe.db.sql("""
        SELECT
            a.name,
            a.purchase_date,
            a.gross_purchase_amount,
            a.total_depreciation_fiscal,
            afb.total_number_of_depreciations
        FROM `tabAsset` a
        LEFT JOIN `tabAsset Finance Book` afb
               ON afb.parent = a.name
              AND afb.idx    = 1
        WHERE a.company               = %(company)s
          AND a.fiscal                = 1
          AND a.calculate_depreciation = 1
          AND a.status                = 'Submitted'
          AND a.docstatus             = 1
        ORDER BY a.asset_category ASC, a.name ASC
    """, {'company': company}, as_dict=True)

    return assets