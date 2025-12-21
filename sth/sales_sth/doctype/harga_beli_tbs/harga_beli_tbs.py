# Copyright (c) 2025, das and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document
from frappe.utils import flt, now_datetime, now

class HargaBeliTBS(Document):
	pass

@frappe.whitelist()
def item_uom_query(doctype, txt, searchfield, start, page_len, filters):
    item_code = filters.get("item_code")

    if not item_code:
        return []

    return frappe.db.sql("""
        SELECT uom.uom
        FROM `tabUOM Conversion Detail` uom
        WHERE uom.parent = %s
          AND uom.uom LIKE %s
        ORDER BY uom.idx
        LIMIT %s OFFSET %s
    """, (
        item_code,
        f"%{txt}%",
        page_len,
        start
    ))

@frappe.whitelist()
def fetch_price_history(item_code, uom):
    if not item_code or not uom:
        return []

    rows = frappe.db.get_all(
        "Item Price Ledger TBS",
        filters={
            "item_code": item_code,
            "uom": uom
        },
        fields=[
            "name",
            "effective_date",
            "old_rate",
            "new_rate",
            "diff",
            "last_update",
            "event_type",
            "remark",
            "unit",
            "supplier",
            "status",
            "approver",
            "jarak"
        ],
        order_by="creation desc",
        limit_page_length=100  
    )

    return [
        {
            "effective_date": r.effective_date,
            "old_price": r.old_rate,
            "price_difference": r.diff,
            "new_price": r.new_rate,
            "last_update": r.last_update,
            "status": r.status,
            "no_transaksi": r.name,
            "unit": r.unit,
            "supplier": r.supplier,
            "approver": r.approver,
            "jarak": r.jarak
        }
        for r in rows
    ]


@frappe.whitelist()
def get_current_price(item_code, uom, price_list=None, supplier=None):

    filters = {
        "item_code": item_code,
        "price_list": price_list,
        "uom": uom,
        "valid_from": ["<=", frappe.utils.nowdate()]
    }

    if supplier:
        filters["supplier"] = supplier

    if price_list:
        filters["price_list"] = price_list

    price = frappe.db.get_all(
        "Item Price",
        filters=filters,
        fields=["price_list_rate", "modified"],
        order_by="valid_from desc, modified desc",
        limit=1
    )

    if price:
        return {
            "rate": price[0].price_list_rate,
            "modified": price[0].modified
        }

    return {
        "rate": 0,
        "modified": None
    }



@frappe.whitelist()
def apply_price_change(item_code, price_list, uom, price_difference, remark=None):
    if not item_code or not price_list or not uom:
        frappe.throw("Item, Price List, dan UOM wajib diisi")

    diff = flt(price_difference)
    if diff == 0:
        frappe.throw("Price Difference tidak boleh 0")

    item_price = frappe.db.get_value(
        "Item Price",
        {
            "item_code": item_code,
            "price_list": price_list,
            "uom": uom
        },
        "name"
    )

    if item_price:
        doc = frappe.get_doc("Item Price", item_price)
        current_rate = flt(doc.price_list_rate or 0)
        new_rate = current_rate + diff

        if new_rate == current_rate:
            frappe.throw("Harga tidak berubah")

        doc.price_list_rate = new_rate
        doc.save()

    else:
        new_rate = diff

        doc = frappe.get_doc({
            "doctype": "Item Price",
            "item_code": item_code,
            "price_list": price_list,
            "uom": uom,
            "price_list_rate": new_rate
        })
        doc.insert()

    if remark:
        frappe.db.set_value(
            "Item Price Ledger TBS",
            {
                "reference_doctype": "Item Price",
                "reference_docname": doc.name,
                "new_rate": new_rate
            },
            "remark",
            remark,
            update_modified=False
        )

    return {
        "rate": new_rate,
        "item_price": doc.name
    }


@frappe.whitelist()
def approve_price_change(ledger_name):
    
    if "Administrator" not in frappe.get_roles():
        frappe.throw("Anda tidak memiliki hak approve harga")

    if not ledger_name:
        frappe.throw("Ledger tidak valid")

    ledger = frappe.get_doc("Item Price Ledger TBS", ledger_name)

    if ledger.status == "Approved":
        frappe.throw("Harga ini sudah di-approve")

    ledger.status = "Approved"
    ledger.approver = frappe.session.user
    ledger.approved_on = now()

    ledger.save(ignore_permissions=True)

    return {
        "status": "success",
        "ledger": ledger.name
    }

@frappe.whitelist()
def create_price_note_from_harga_beli_tbs(
    item_code, unit, supplier, jarak, uom, current_rate, price_difference
):
    if not item_code or not unit or not supplier:
        frappe.throw("Item Code, Unit, dan Supplier wajib diisi")

    PRICE_PRECISION = 2

    current_rate = flt(current_rate, PRICE_PRECISION)
    price_difference = flt(price_difference, PRICE_PRECISION)

    if current_rate < 0:
        frappe.throw("Current Rate tidak valid")

    if price_difference == 0:
        frappe.throw("Price Difference tidak boleh 0")

    new_rate = flt(current_rate + price_difference, PRICE_PRECISION)

    if new_rate <= 0:
        frappe.throw("New Rate tidak valid")

    jarak = (jarak or "").strip()

    if jarak:
        target_price_lists = [f"{unit} - {jarak}"]
    else:
        target_price_lists = [
            f"{unit} - RING 1",
            f"{unit} - RING 2"
        ]

    price_list_value = ", ".join(target_price_lists)

    frappe.get_doc({
        "doctype": "Item Price Ledger TBS",
        "item_code": item_code,
        "unit": unit,
        "supplier": supplier,
        "uom": uom,

        "jarak": jarak or None,        
        "price_list": price_list_value,  

        "old_rate": current_rate,
        "new_rate": new_rate,
        "diff": price_difference,

        "status": "Pending",
        "last_update": frappe.session.user,
        "effective_date": now(),
    }).insert(ignore_permissions=True)

    return {
        "status": "success",
        "price_list": price_list_value,
        "message": "Request perubahan harga berhasil dibuat dan menunggu approval"
    }
