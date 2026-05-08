import frappe
from frappe import _

@frappe.whitelist()
def check_invoice_asuransi_sewa(self,method):
    """
    Cek Purchase Invoice (SEWA / ASURANSI) dalam periode closing
    yang belum dibuatkan Transaksi Berulang.
    """

    result = frappe.db.sql("""
        SELECT
            pi.name,
            pi.supplier,
            pi.posting_date,
            pi.grand_total,
            pi.invoice_type
        FROM `tabPurchase Invoice` pi
        LEFT JOIN `tabTransaksi Berulang` tb
            ON tb.tarik_purchase_invoice = pi.name
        WHERE pi.invoice_type IN ('Sewa', 'Asuransi')
          AND pi.docstatus = 1
          AND pi.company = %(company)s
          AND pi.posting_date BETWEEN %(start)s AND %(end)s
          AND tb.tarik_purchase_invoice IS NULL
    """, {
        'company':  self.company,
        'start':    self.period_start_date,
        'end':      self.period_end_date,
    }, as_dict=True)

    if result:
        rows = "".join([
            f"<tr><td>{r.name}</td><td>{r.supplier}</td><td>{r.invoice_type}</td><td>{r.posting_date}</td></tr>"
            for r in result
        ])

        frappe.throw(
            title=_("Invoice Belum Dibuatkan Transaksi Berulang"),
            msg=_("""
                <p>Closing periode tidak dapat dilanjutkan. Masih terdapat invoice <b>SEWA / ASURANSI</b> 
                yang belum dibuatkan <b>Transaksi Berulang</b>:</p>
                <table class="table table-bordered table-sm" style="margin-top:8px;">
                    <thead>
                        <tr>
                            <th>Invoice</th>
                            <th>Supplier</th>
                            <th>Jenis</th>
                            <th>Tanggal</th>
                        </tr>
                    </thead>
                    <tbody>{rows}</tbody>
                </table>
                <p>Silakan buat Transaksi Berulang terlebih dahulu sebelum melakukan closing.</p>
            """).format(rows=rows)
        )

@frappe.whitelist()
def check_invoice_asuransi_sewa_accounting_period(self,method):
    """
    Cek Purchase Invoice (SEWA / ASURANSI) dalam periode closing
    yang belum dibuatkan Transaksi Berulang.
    """

    result = frappe.db.sql("""
        SELECT
            pi.name,
            pi.supplier,
            pi.posting_date,
            pi.grand_total,
            pi.invoice_type
        FROM `tabPurchase Invoice` pi
        LEFT JOIN `tabTransaksi Berulang` tb
            ON tb.tarik_purchase_invoice = pi.name
        WHERE pi.invoice_type IN ('Sewa', 'Asuransi')
          AND pi.docstatus = 1
          AND pi.company = %(company)s
          AND pi.posting_date BETWEEN %(start)s AND %(end)s
          AND tb.tarik_purchase_invoice IS NULL
    """, {
        'company':  self.company,
        'start':    self.start_date,
        'end':      self.end_date,
    }, as_dict=True)

    if result:
        rows = "".join([
            f"<tr><td>{r.name}</td><td>{r.supplier}</td><td>{r.invoice_type}</td><td>{r.posting_date}</td></tr>"
            for r in result
        ])

        frappe.throw(
            title=_("Invoice Belum Dibuatkan Transaksi Berulang"),
            msg=_("""
                <p>Closing periode tidak dapat dilanjutkan. Masih terdapat invoice <b>SEWA / ASURANSI</b> 
                yang belum dibuatkan <b>Transaksi Berulang</b>:</p>
                <table class="table table-bordered table-sm" style="margin-top:8px;">
                    <thead>
                        <tr>
                            <th>Invoice</th>
                            <th>Supplier</th>
                            <th>Jenis</th>
                            <th>Tanggal</th>
                        </tr>
                    </thead>
                    <tbody>{rows}</tbody>
                </table>
                <p>Silakan buat Transaksi Berulang terlebih dahulu sebelum melakukan closing.</p>
            """).format(rows=rows)
        )
