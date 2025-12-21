# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, now, nowdate


class ItemPriceLedgerTBS(Document):

    def autoname(self):
        date_part = now().replace("-", "")[:8]
        unit = self.unit or ""

        count = frappe.db.count(
            "Item Price Ledger TBS",
            filters={
                "unit": unit,
                "name": ["like", f"{date_part}/{unit}/%"]
            }
        )

        seq = str(count + 1).zfill(4)
        self.name = f"{date_part}/{unit}/{seq}"

    def on_update(self):
        if self.status == "Approved" and not self.applied_to_item_price:
            self.safe_apply_to_item_price()

    def safe_apply_to_item_price(self):
        try:
            self.apply_to_item_price()

        except Exception:
            frappe.db.set_value(
                self.doctype,
                self.name,
                {
                    "status": "Pending",
                    "applied_to_item_price": 0
                },
                update_modified=False
            )

            frappe.log_error(
                title="Item Price Ledger TBS Approval Failed",
                message=frappe.get_traceback()
            )

            frappe.throw(
                "Gagal meng-apply Item Price. "
                "Status dikembalikan ke Pending. "
                "Silakan cek Error Log."
            )

    def apply_to_item_price(self):
        if not self.price_list:
            frappe.throw("Price List kosong, tidak bisa apply harga")

        price_lists = [
            pl.strip()
            for pl in self.price_list.split(",")
            if pl.strip()
        ]

        for price_list in price_lists:
            self.create_or_update_item_price(price_list)

        self.applied_to_item_price = 1
        self.applied_on = now()

        self.db_update()

    def create_or_update_item_price(self, price_list):
        self.ensure_price_list(price_list)

        filters = {
            "item_code": self.item_code,
            "price_list": price_list,
            "uom": self.uom,
            "supplier": self.supplier
        }

        existing = frappe.db.get_value(
            "Item Price",
            filters,
            ["name"],
            as_dict=True
        )

        if existing:
            frappe.db.set_value(
                "Item Price",
                existing.name,
                "price_list_rate",
                flt(self.new_rate)
            )
        else:
            frappe.get_doc({
                "doctype": "Item Price",
                "item_code": self.item_code,
                "price_list": price_list,
                "uom": self.uom,
                "supplier": self.supplier,
                "price_list_rate": flt(self.new_rate),
                "valid_from": nowdate()
            }).insert(ignore_permissions=True)


    def ensure_price_list(self, price_list_name):
        if frappe.db.exists("Price List", price_list_name):
            return

        frappe.get_doc({
            "doctype": "Price List",
            "price_list_name": price_list_name,
            "selling": 0,
            "buying": 1,
            "enabled": 1
        }).insert(ignore_permissions=True)