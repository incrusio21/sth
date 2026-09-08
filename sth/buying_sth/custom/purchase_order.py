# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt, cint, nowdate
    
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
            "Purchase Taxes and Charges": {
                "doctype": "Purchase Taxes and Charges",
                "reset_value": True,
                "condition": lambda doc: not (doc.description or "").startswith("__from_ppn__"),
            },
        },
        target_doc,
        set_missing_values,
    )

    return doc


@frappe.whitelist()
def check_uang_muka_payment_entry(purchase_order):
    """Sisa uang muka PO, dipakai menahan PO ditutup selagi uangnya masih di supplier.

    Dulu yang dilihat cuma ada-tidaknya GL Entry uang muka dari Payment Entry,
    dicari dari nama akun yang mengandung "UANG MUKA". Akibatnya PO tetap
    tertahan walaupun uang mukanya sudah habis dipakai invoice atau sudah
    dikembalikan ke supplier. Yang dipakai sekarang sisanya, dihitung dari baris
    pembayarannya sendiri, bukan ditebak dari nama akun.
    """
    from sth.buying_sth.custom.uang_muka_po import rekap_uang_muka_po

    rekap = rekap_uang_muka_po(purchase_order)

    return {
        'has_uang_muka': flt(rekap['total_dibayar']) > 0,
        'has_payment_entry': flt(rekap['sisa']) > 0,
        'sisa': flt(rekap['sisa']),
    }


@frappe.whitelist()
def info_uang_muka_po(purchase_order):
    """Rincian uang muka satu PO untuk ditampilkan di form Purchase Order."""
    frappe.has_permission("Purchase Order", doc=purchase_order, throw=True)

    from sth.buying_sth.custom.uang_muka_po import rekap_uang_muka_po

    return rekap_uang_muka_po(purchase_order)


@frappe.whitelist()
def get_payment_entry_pengembalian_uang_muka(purchase_order, jumlah=None):
    """Payment Entry penerimaan yang menarik balik sisa uang muka Purchase Order.

    Uang mukanya tidak dibatalkan: Payment Entry pembayarannya tetap utuh
    menempel di PO, begitu juga jurnalnya. Pengembaliannya jadi dokumen sendiri
    yang mengkredit akun uang muka yang sama dengan `against_voucher` PO yang
    sama, jadi saldo uang muka supplier tertutup lewat payment ledger dan
    advance_paid PO ikut turun tanpa satu pun jurnal lama diposting ulang.

    Rekening penerimaannya sengaja dibiarkan kosong — diisi user lewat Unit dan
    Mode of Payment seperti Payment Entry lain, supaya uangnya masuk ke rekening
    yang benar-benar menerima.
    """
    from erpnext.setup.utils import get_exchange_rate

    from sth.buying_sth.custom.uang_muka_po import akun_uang_muka_tersisa, rekap_uang_muka_po

    frappe.has_permission("Purchase Order", doc=purchase_order, throw=True)

    rekap = rekap_uang_muka_po(purchase_order)
    sisa = flt(rekap['sisa'])

    if sisa <= 0:
        frappe.throw(
            _("Purchase Order {0} tidak punya sisa uang muka yang bisa dikembalikan.").format(
                purchase_order
            ),
            title=_("Uang Muka PO"),
        )

    jumlah = flt(jumlah) if jumlah else sisa

    if jumlah <= 0:
        frappe.throw(_("Jumlah pengembalian harus lebih dari nol."), title=_("Uang Muka PO"))

    if jumlah > sisa:
        frappe.throw(
            _("Jumlah pengembalian ({0}) melebihi sisa uang muka {1} ({2}).").format(
                frappe.format_value(jumlah, {"fieldtype": "Currency"}),
                purchase_order,
                frappe.format_value(sisa, {"fieldtype": "Currency"}),
            ),
            title=_("Uang Muka PO"),
        )

    po = frappe.get_doc("Purchase Order", purchase_order)
    akun = akun_uang_muka_tersisa(purchase_order)
    mata_uang_akun = frappe.db.get_value("Account", akun, "account_currency")
    mata_uang_company = frappe.get_cached_value("Company", po.company, "default_currency")

    kurs = 1.0
    if mata_uang_akun != mata_uang_company:
        kurs = get_exchange_rate(mata_uang_akun, mata_uang_company, nowdate())

    pe = frappe.new_doc("Payment Entry")
    pe.payment_type = "Receive"
    pe.company = po.company
    pe.posting_date = nowdate()
    pe.party_type = "Supplier"
    pe.party = po.supplier
    pe.party_name = po.supplier_name
    pe.unit = po.get("unit")
    pe.cost_center = po.get("cost_center")
    pe.paid_from = akun
    pe.paid_from_account_currency = mata_uang_akun
    pe.source_exchange_rate = kurs
    pe.target_exchange_rate = kurs
    pe.paid_amount = jumlah
    pe.received_amount = jumlah
    pe.base_paid_amount = jumlah * kurs
    pe.base_received_amount = jumlah * kurs
    pe.total_allocated_amount = jumlah
    pe.base_total_allocated_amount = jumlah * kurs
    pe.unallocated_amount = 0
    pe.difference_amount = 0
    pe.remarks = _("Pengembalian uang muka Purchase Order {0}").format(po.name)

    pe.append(
        "references",
        {
            "reference_doctype": "Purchase Order",
            "reference_name": po.name,
            "total_amount": po.rounded_total or po.grand_total,
            "outstanding_amount": sisa,
            "allocated_amount": jumlah,
            "exchange_rate": kurs,
        },
    )

    pe.setup_party_account_field()

    return pe


def tipe_procurement_po(sub_purchase_type):
    """Jenis PO dalam istilah tabel Procurement Settings.

    Patokan yang sama dipakai Purchase Invoice saat memilih akun uang muka termin
    DP: hanya Service Request yang dihitung jasa. PO Capex tidak mengisi
    sub_purchase_type sama sekali, jadi ikut barang.
    """
    return "jasa" if sub_purchase_type == "Service Request" else "barang"


def akun_uang_muka_po(purchase_orders, company):
    """Akun Uang Muka untuk sekumpulan PO, dari Procurement Settings.

    Melempar kalau PO barang dan jasa dicampur dalam satu pembayaran — akun uang
    muka keduanya berbeda, jadi tidak ada satu akun yang benar untuk dipakai.
    """
    from sth.custom.method_ambil_account import ambil_uang_muka_procurement

    tipe = {
        tipe_procurement_po(
            frappe.db.get_value("Purchase Order", nama, "sub_purchase_type")
        )
        for nama in purchase_orders
    }

    if len(tipe) > 1:
        frappe.throw(
            _("Purchase Order barang dan jasa tidak bisa dibayar dalam satu Payment Entry "
              "karena akun uang mukanya berbeda. Pisahkan pembayarannya."),
            title=_("Jenis PO Bercampur"),
        )

    return ambil_uang_muka_procurement(tipe.pop(), company)


@frappe.whitelist()
def get_payment_entry_uang_muka(
    dt,
    dn,
    party_amount=None,
    bank_account=None,
    bank_amount=None,
    party_type=None,
    payment_type=None,
    reference_date=None,
):
    """Payment Entry dari Purchase Order dengan paid_to akun Uang Muka.

    get_payment_entry bawaan ERPNext memasang akun hutang usaha supplier di
    paid_to. Pembayaran terhadap PO belum ada tagihannya — uangnya uang muka,
    jadi akunnya diambil dari Procurement Settings sesuai jenis PO.

    Supplier-nya tetap terpasang supaya baris referensi ke PO tetap sah; akun
    uang muka bukan Payable sehingga party-nya dilepas saat jurnal dibuat oleh
    add_party_gl_entries.

    Parameternya ditulis satu per satu, bukan **kwargs: frappe meneruskan seluruh
    form_dict ke fungsi ber-**kwargs, termasuk cmd, dan get_payment_entry tidak
    menerimanya.
    """
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

    pe = get_payment_entry(
        dt,
        dn,
        party_amount=party_amount,
        bank_account=bank_account,
        bank_amount=bank_amount,
        party_type=party_type,
        payment_type=payment_type,
        reference_date=reference_date,
    )

    if dt == "Purchase Order":
        pe.paid_to = akun_uang_muka_po([dn], pe.company)
        pe.paid_to_account_currency = frappe.db.get_value(
            "Account", pe.paid_to, "account_currency"
        )

    return pe


def set_accept_day(doc,method):
    doc.accept_day = cint(doc.syarat_pembayaran.split(' ')[0]) if doc.syarat_pembayaran else 0

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
