from frappe.utils import get_defaults
from num2words import num2words
import frappe
from datetime import datetime

def money_in_words_idr(
    number,  # bisa Union[str, float, int]
    main_currency=None,
    fraction_currency=None
):
    try:
        number = int(round(float(number)))
    except (ValueError, TypeError):
        return ""

    return f"{num2words(number, lang='id')} rupiah"

def format_tanggal_id(tanggal):
    if not tanggal:
        return ""

    bulan = {
        1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
        5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
        9: "September", 10: "Oktober", 11: "November", 12: "Desember"
    }

    if isinstance(tanggal, str):
        tanggal = frappe.utils.getdate(tanggal)

    return f"{tanggal.day} {bulan[tanggal.month]} {tanggal.year}"

def sum_pengakuan_penjualan_by_nota_piutang(nota_piutang=None):
    return frappe.db.sql("""
    SELECT
    nppkt.pengakuan_penjualan,
    nppkt.posting_date as date,
    SUM(nppkt.qty) as qty,
    si.komoditi as descriptions,
    SUM(nppkt.rate) as price,
    SUM(nppkt.subtotal) as amount
    FROM `tabNota Piutang` as np
    JOIN `tabNota Piutang Pemenuhan Kontrak Table` as nppkt ON nppkt.parent = np.name
    LEFT JOIN `tabSales Invoice` as si ON si.name = nppkt.pengakuan_penjualan
    WHERE np.name = %s;
    """, (nota_piutang), as_dict=1)[0]

def get_payment_entry_ledger_preview(docname):
    import frappe
    
    docstatus = frappe.db.get_value("Payment Entry", docname, "docstatus")
    
    if docstatus == 1:
        return frappe.db.sql("""
            SELECT
                a.account_number,
                gle.account,
                gle.debit,
                gle.credit
            FROM `tabGL Entry` gle
            JOIN `tabAccount` a ON a.name = gle.account
            WHERE gle.voucher_no = %s
            AND gle.is_cancelled = 0
        """, (docname,), as_dict=1)
    else:
        pe = frappe.get_doc("Payment Entry", docname)
        pe.docstatus = 1  # set di memory saja
        gl_map = pe.build_gl_map()
        
        return [{
            "account_number": frappe.db.get_value("Account", e.get("account"), "account_number") or "",
            "account": e.get("account", ""),
            "debit": e.get("debit", 0),
            "credit": e.get("credit", 0),
        } for e in gl_map]