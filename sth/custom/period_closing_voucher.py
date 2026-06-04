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
def check_invoice_asuransi_sewa_accounting_period(self, method):
    """
    Cek Purchase Invoice (SEWA / ASURANSI) yang belum dibuatkan Transaksi Berulang,
    dan Surat Jalan yang belum berstatus 'Terkirim', dalam periode closing.
    """
    pinv_result = frappe.db.sql("""
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
        'company': self.company,
        'start':   self.start_date,
        'end':     self.end_date,
    }, as_dict=True)

    sj_result = frappe.db.sql("""
        SELECT
            sj.name,
            sj.diterima_oleh as customer,
            sj.tanggal_transaksi as posting_date,
            sj.status
        FROM `tabSurat Jalan` sj
        WHERE sj.docstatus = 1
          AND sj.company = %(company)s
          AND sj.tanggal_transaksi BETWEEN %(start)s AND %(end)s
          AND sj.status != 'Diterima'
    """, {
        'company': self.company,
        'start':   self.start_date,
        'end':     self.end_date,
    }, as_dict=True)

    if not pinv_result and not sj_result:
        return

    msg = ""

    if pinv_result:
        pinv_rows = "".join([
            f"<tr><td>{r.name}</td><td>{r.supplier}</td><td>{r.invoice_type}</td><td>{r.posting_date}</td></tr>"
            for r in pinv_result
        ])
        msg += """
            <p>Masih terdapat invoice <b>SEWA / ASURANSI</b> yang belum dibuatkan <b>Transaksi Berulang</b>:</p>
            <table class="table table-bordered table-sm" style="margin-top:8px;">
                <thead>
                    <tr>
                        <th>Invoice</th>
                        <th>Supplier</th>
                        <th>Jenis</th>
                        <th>Tanggal</th>
                    </tr>
                </thead>
                <tbody>{pinv_rows}</tbody>
            </table>
        """.format(pinv_rows=pinv_rows)

    if sj_result:
        sj_rows = "".join([
            f"<tr><td>{r.name}</td><td>{r.customer}</td><td>{r.posting_date}</td><td>{r.status}</td></tr>"
            for r in sj_result
        ])
        msg += """
            <p style="margin-top:16px;">Masih terdapat <b>Surat Jalan</b> yang belum berstatus <b>Diterima</b>:</p>
            <table class="table table-bordered table-sm" style="margin-top:8px;">
                <thead>
                    <tr>
                        <th>Surat Jalan</th>
                        <th>Customer</th>
                        <th>Tanggal</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>{sj_rows}</tbody>
            </table>
        """.format(sj_rows=sj_rows)

    frappe.throw(
        title=_("Closing Periode Tidak Dapat Dilanjutkan"),
        msg=_("""
            <p>Closing periode tidak dapat dilanjutkan karena:</p>
            {msg}
            <p style="margin-top:12px;">Silakan selesaikan item-item di atas sebelum melakukan closing.</p>
        """).format(msg=msg)
    )