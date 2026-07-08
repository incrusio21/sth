import frappe
from frappe.model.document import Document


class CostingTraksi(Document):

    def before_save(self):
        self.hitung_total()

    def hitung_total(self):
        self.total_pengeluaran_barang = sum(d.total or 0 for d in self.pengeluaran_barang_items)
        self.total_bkmt = sum(d.total or 0 for d in self.bkmt_items)
        self.grand_total = (self.total_pengeluaran_barang or 0) + (self.total_bkmt or 0)


@frappe.whitelist()
def get_pengeluaran_barang_traksi(periode_dari, periode_sampai):
    """
    Ambil Pengeluaran Barang yang itemnya memiliki sub_unit = TRAKSI,
    hitung total nilai dari Stock Ledger Entry via ste_reference.
    """
    pb_list = frappe.db.sql("""
        SELECT DISTINCT pb.name, pb.tanggal, pb.ste_reference
        FROM `tabPengeluaran Barang` pb
        INNER JOIN `tabPengeluaran Barang Item` pbi ON pbi.parent = pb.name
        WHERE pb.docstatus = 1
          AND pb.tanggal BETWEEN %(dari)s AND %(sampai)s
          AND pbi.sub_unit = 'TRAKSI'
        ORDER BY pb.tanggal, pb.name
    """, {"dari": periode_dari, "sampai": periode_sampai}, as_dict=True)

    result = []
    for pb in pb_list:
        total = 0.0

        if pb.ste_reference:
            sle_total = frappe.db.sql("""
                SELECT ABS(SUM(stock_value_difference)) as total
                FROM `tabStock Ledger Entry`
                WHERE voucher_type = 'Stock Entry'
                  AND voucher_no = %(ste)s
                  AND stock_value_difference < 0
            """, {"ste": pb.ste_reference}, as_dict=True)

            if sle_total and sle_total[0].total:
                total = sle_total[0].total

        result.append({
            "no_dokumen": pb.name,
            "total": total
        })

    return result


@frappe.whitelist()
def get_bkmt_traksi(periode_dari, periode_sampai):
    """
    Ambil Buku Kerja Mandor Traksi yang sudah submit dalam periode,
    dengan divisi = TRAKSI. Total diambil dari field grand_total.
    """
    bkmt_list = frappe.db.sql("""
        SELECT name, grand_total
        FROM `tabBuku Kerja Mandor Traksi`
        WHERE docstatus = 1
          AND posting_date BETWEEN %(dari)s AND %(sampai)s
          AND divisi = 'TRAKSI'
        ORDER BY posting_date, name
    """, {"dari": periode_dari, "sampai": periode_sampai}, as_dict=True)

    result = []
    for bkmt in bkmt_list:
        result.append({
            "no_dokumen": bkmt.name,
            "total": bkmt.grand_total or 0.0
        })

    return result
