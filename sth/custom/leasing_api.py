import frappe
from frappe.utils import flt


@frappe.whitelist()
def get_leasing_rows(docname: str) -> dict:
    """
    Kembalikan baris leasing yang belum dibayar dari dokumen Transaksi Berulang.
    Dipanggil dari client script Payment Entry.

    Return:
        {
            "rows": [ {idx, tenor, tanggal_angsuran, angsuran, bunga, saldo}, ... ],
            "meta": { jurnal_kredit, jurnal_debit, biaya_bunga_leasing_debit }
        }
    """
    doc = frappe.get_doc("Transaksi Berulang", docname)

    rows = []
    for row in doc.transaksi_berulang_leasing_table:
        status = (row.status_bayar or "Belum Dibayar").strip()
        if status == "Belum Dibayar":
            rows.append({
                "idx"              : row.idx,
                "tenor"            : row.tenor,
                "tanggal_angsuran" : str(row.tanggal_angsuran),
                "angsuran"         : flt(row.angsuran),
                "bunga"            : flt(row.bunga),
                "saldo"            : flt(row.saldo),
                "no_transfer"      : row.no_transfer
            })

    meta = {
        "jurnal_kredit"             : doc.jurnal_kredit,
        "jurnal_debit"              : doc.jurnal_debit,
        "biaya_bunga_leasing_debit" : getattr(doc, "biaya_bunga_leasing_debit", None),
    }

    return {"rows": rows, "meta": meta}