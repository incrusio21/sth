# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from erpnext.controllers.taxes_and_totals import init_landed_taxes_and_totals
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry

class StockEntry(StockEntry):
    def calculate_rate_and_amount(self, reset_outgoing_rate=True, raise_error_if_no_rate=True):
        self.set_basic_rate(reset_outgoing_rate, raise_error_if_no_rate)
        init_landed_taxes_and_totals(self)
        self.distribute_additional_costs()
        self.update_valuation_rate()
        self.set_total_incoming_outgoing_value()
        self.set_total_amount()

        self.set_bkm_rate()

    def set_bkm_rate(self):
        # Set rate for buku kerja mandor
        if bkm := frappe.get_value("Buku Kerja Mandor Perawatan", {"stock_entry": self.name}, "name"):
            doc = frappe.get_doc("Buku Kerja Mandor Perawatan", bkm)
            doc.set_material_rate()