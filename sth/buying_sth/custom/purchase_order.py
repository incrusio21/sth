# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt
    
@frappe.whitelist()
def make_purchase_receipt(source_name, target_doc=None):
    has_unit_price_items = frappe.db.get_value("Purchase Order", source_name, "has_unit_price_items")

    def set_missing_values(source, target):
        target.purchase_type = frappe.get_value("Purchase Type", source.purchase_type, "future_type")

        target.run_method("set_missing_values")
        target.run_method("calculate_taxes_and_totals")
        
    def is_unit_price_row(source):
        return has_unit_price_items and source.qty == 0
    
    def update_item(obj, target, source_parent):
        target.qty = flt(obj.qty) if is_unit_price_row(obj) else flt(obj.qty) - flt(obj.received_qty)
        target.stock_qty = (flt(obj.qty) - flt(obj.received_qty)) * flt(obj.conversion_factor)
        target.amount = (flt(obj.qty) - flt(obj.received_qty)) * flt(obj.rate)
        target.base_amount = (
            (flt(obj.qty) - flt(obj.received_qty)) * flt(obj.rate) * flt(source_parent.conversion_rate)
        )

        # add mapping
        target.po_qty = obj.qty

    doc = get_mapped_doc(
        "Purchase Order",
        source_name,
        {
            "Purchase Order": {
                "doctype": "Purchase Receipt",
                "field_map": {"supplier_warehouse": "supplier_warehouse"},
                "validation": {
                    "docstatus": ["=", 1],
                },
            },
            "Purchase Order Item": {
                "doctype": "Purchase Receipt Item",
                "field_map": {
                    "name": "purchase_order_item",
                    "parent": "purchase_order",
                    "bom": "bom",
                    "material_request": "material_request",
                    "material_request_item": "material_request_item",
                    "sales_order": "sales_order",
                    "sales_order_item": "sales_order_item",
                    "wip_composite_asset": "wip_composite_asset",
                },
                "postprocess": update_item,
                "condition": lambda doc: (
                    True if is_unit_price_row(doc) else abs(doc.received_qty) < abs(doc.qty)
                )
                and doc.delivered_by_supplier != 1,
            },
            "Purchase Taxes and Charges": {"doctype": "Purchase Taxes and Charges", "reset_value": True},
        },
        target_doc,
        set_missing_values,
    )

    return doc


@frappe.whitelist()
def check_uang_muka_payment_entry(purchase_order):
    """Check if Purchase Order has GL Entry for Uang Muka with Payment Entry"""
    
    gl_entries = frappe.db.sql("""
        SELECT 
            ge.name, 
            ge.voucher_no, 
            ge.voucher_type,
            ge.account
        FROM `tabGL Entry` ge
        WHERE ge.against_voucher = %(po_name)s
            AND ge.against_voucher_type = 'Purchase Order'
            AND ge.account LIKE %(account_pattern)s
            AND is_cancelled = 0
    """, {
        'po_name': purchase_order,
        'account_pattern': '%UANG MUKA%'
    }, as_dict=1,debug=1)
    
    has_payment_entry = any(
        entry.get('voucher_type') == 'Payment Entry' 
        for entry in gl_entries
    )
    
    return {
        'has_uang_muka': len(gl_entries) > 0,
        'has_payment_entry': has_payment_entry
    }

def set_accept_day(doc,method):
    doc.accept_day = int(doc.syarat_pembayaran.split(' ')[0]) if doc.syarat_pembayaran else 0

@frappe.whitelist()
def get_history_purchase_item(nama_barang):
    from erpnext.accounts.utils import get_fiscal_year
    today = frappe.utils.today()
    fiscal_year = get_fiscal_year(date=today,boolean=True)
    start_year = fiscal_year[0][1]

    return frappe.db.sql("""
        SELECT poi.item_code, poi.item_name, po.name as no_po, po.transaction_date as tanggal_po, poi.qty, poi.custom_merk as merk, 
        poi.custom_country as country,poi.description, po.currency, poi.rate, poi.amount, s.supplier_name, poi.material_request, po.keterangan, 
        mr.transaction_date as tanggal_pr_sr
        FROM `tabPurchase Order` po 
        JOIN `tabSupplier` s on s.name = po.supplier
        JOIN `tabPurchase Order Item` poi on poi.parent = po.name
        JOIN `tabMaterial Request` mr on mr.name = poi.material_request
        WHERE po.docstatus = 1 AND poi.item_name = %s AND po.transaction_date BETWEEN %s AND %s
        ORDER BY po.transaction_date, po.name
    """,(nama_barang,start_year,today),as_dict=True)

@frappe.whitelist()
def get_history_service_request(asset):
    from erpnext.accounts.utils import get_fiscal_year
    today = frappe.utils.today()
    fiscal_year = get_fiscal_year(date=today,boolean=True)
    start_year = fiscal_year[0][1]

    return frappe.db.sql("""
        SELECT poi.item_code, poi.item_name, po.name as no_po, po.transaction_date as tanggal, poi.qty, poi.rate, poi.amount, s.supplier_name, poi.material_request, mri.km_hm
        FROM `tabPurchase Order` po 
        JOIN `tabPurchase Order Item` poi on poi.parent = po.name
        JOIN `tabMaterial Request Item` mri on mri.name = poi.material_request_item
        WHERE po.docstatus = 1 AND mr.kendaraan = %s AND mr.transaction_date BETWEEN %s AND %s
    """,(asset,start_year,today),as_dict=True)
