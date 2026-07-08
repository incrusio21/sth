import erpnext
import frappe
from erpnext.accounts.general_ledger import make_gl_entries, make_reverse_gl_entries
from frappe.model.document import Document


class CostingBengkel(Document):

    def before_save(self):
        self.hitung_total()

    def on_submit(self):
        self.make_gl_entry()

    def on_cancel(self):
        self.ignore_linked_doctypes = ("GL Entry",)
        self.make_gl_entry()

    def on_trash(self):
        frappe.db.delete("GL Entry", {
            "voucher_type": self.doctype,
            "voucher_no": self.name,
        })

    def make_gl_entry(self):
        if self.docstatus == 1:
            make_gl_entries(self.get_gl_entries(), merge_entries=False)
        elif self.docstatus == 2:
            make_reverse_gl_entries(voucher_type=self.doctype, voucher_no=self.name)

    def get_gl_entries(self):
        gl_entries = []
        default_cost_center = erpnext.get_default_cost_center(self.company)

        for row in self.costing_bengkel_closing_bengkel:
            cost_center = get_or_create_cost_center(row.kode_vra, self.company) if row.kode_vra else default_cost_center

            if row.debit:
                gl_entries.append(self.get_gl_dict({
                    "account": row.no_coa,
                    "cost_center": cost_center,
                    "debit": row.debit,
                    "debit_in_account_currency": row.debit,
                    "remarks": row.keterangan,
                }))
            if row.credit:
                gl_entries.append(self.get_gl_dict({
                    "account": row.no_coa,
                    "cost_center": cost_center,
                    "credit": row.credit,
                    "credit_in_account_currency": row.credit,
                    "remarks": row.keterangan,
                }))

        for row in self.costing_bengkel_closing_vra:
            cost_center = get_or_create_cost_center(row.kode_vra, self.company) if row.kode_vra else default_cost_center

            if row.debit:
                gl_entries.append(self.get_gl_dict({
                    "account": row.no_coa,
                    "cost_center": cost_center,
                    "debit": row.debit,
                    "debit_in_account_currency": row.debit,
                    "remarks": row.keterangan,
                }))
            if row.credit:
                gl_entries.append(self.get_gl_dict({
                    "account": row.no_coa,
                    "cost_center": cost_center,
                    "credit": row.credit,
                    "credit_in_account_currency": row.credit,
                    "remarks": row.keterangan,
                }))

        return gl_entries

    def get_gl_dict(self, args):
        gl_dict = frappe._dict({
            "company": self.company,
            "posting_date": self.periode_sampai,
            "voucher_type": self.doctype,
            "voucher_no": self.name,
            "remarks": "Costing Bengkel {0}".format(self.name),
            "against": None,
            "debit": 0,
            "credit": 0,
            "debit_in_account_currency": 0,
            "credit_in_account_currency": 0,
            "is_opening": "No",
            "party_type": None,
            "party": None,
            "cost_center": None,
            "company_currency": erpnext.get_company_currency(self.company),
        })
        gl_dict.update(args)
        return gl_dict

    def hitung_total(self):
        self.total_pengeluaran_barang = sum(d.amount or 0 for d in self.costing_bengkel_pengeluaran_barang)
        self.total_pengeluaran_barang_solar = sum(d.amount or 0 for d in self.costing_bengkel_pengeluaran_barang_solar)
        self.total_payslip_karyawan_bengkel = sum(d.amount or 0 for d in self.costing_bengkel_payslip_karyawan_bengkel)
        self.total_alokasi_gaji_karyawan_bengkel = sum(d.amount or 0 for d in self.costing_bengkel_alokasi_gaji_karyawan_bengkel)
        self.total_payslip_operator_vra = sum(d.amount or 0 for d in self.costing_bengkel_payslip_operator_vra)
        self.total_alokasi_gaji_operator_vra = sum(d.amount or 0 for d in self.costing_bengkel_alokasi_gaji_operator_vra)
        self.total_closing_vra = sum(d.debit or 0 for d in self.costing_bengkel_closing_vra)
        self.total_gl_bkm_traksi = sum(d.debit or 0 for d in self.costing_bengkel_gl_bkm_traksi)
        self.grand_total = (
            (self.total_pengeluaran_barang or 0)
            + (self.total_pengeluaran_barang_solar or 0)
            + (self.total_payslip_karyawan_bengkel or 0)
            + (self.total_alokasi_gaji_karyawan_bengkel or 0)
            + (self.total_payslip_operator_vra or 0)
            + (self.total_alokasi_gaji_operator_vra or 0)
        )


def get_or_create_cost_center(kode_vra, company):
    """
    Ambil Cost Center dengan nama = kode_vra untuk company terkait.
    Kalau belum ada (mis. kendaraan belum sempat membuat cost center-nya sendiri),
    buat otomatis mengikuti pola yang sama seperti Alat Berat Dan Kendaraan.
    """
    existing = frappe.db.get_value("Cost Center", {"cost_center_name": kode_vra, "company": company}, "name")
    if existing:
        return existing

    company_doc = frappe.get_cached_doc("Company", company)

    cc = frappe.new_doc("Cost Center")
    cc.cost_center_name = kode_vra
    cc.parent_cost_center = "Main - {0}".format(company_doc.abbr)
    cc.company = company
    cc.is_group = 0
    cc.flags.ignore_permissions = True
    cc.insert()

    return cc.name


@frappe.whitelist()
def get_pengeluaran_barang_bengkel(periode_dari, periode_sampai, company=None, unit=None):
    """
    Ambil Pengeluaran Barang Item yang sub_unit = BENGKEL dan punya kendaraan (asset),
    hitung nilai per item dari Stock Ledger Entry berdasarkan STE reference + item_code.
    Return breakdown per kendaraan + COA.
    """
    company_filter = "AND pb.pt_pemilik_barang = %(company)s" if company else ""
    unit_filter = "AND pb.unit = %(unit)s" if unit else ""
    pb_items = frappe.db.sql("""
        SELECT
            pb.name AS no_pb,
            ste.name as ste_reference,
            pbi.kode_barang,
            pbi.item_name,
            pbi.kendaraan,
            pbi.account
        FROM `tabPengeluaran Barang` pb
        JOIN `tabPengeluaran Barang Item` pbi ON pbi.parent = pb.name
        JOIN `tabStock Entry` ste ON ste.pengeluaran_barang = pb.name AND ste.docstatus = 1
        WHERE pb.docstatus = 1
          AND pb.tanggal BETWEEN %(dari)s AND %(sampai)s
          AND pbi.sub_unit = 'BENGKEL'
          AND pbi.kendaraan != ''
          AND pbi.kendaraan IS NOT NULL
          AND pbi.account LIKE '%%4111004%%'
          {company_filter}
          {unit_filter}
        ORDER BY pb.tanggal, pb.name, pbi.kendaraan;
    """.format(company_filter=company_filter, unit_filter=unit_filter), {"dari": periode_dari, "sampai": periode_sampai, "company": company, "unit": unit}, as_dict=True)

    result = []
    for item in pb_items:
        amount = 0.0

        if item.ste_reference:
            sle = frappe.db.sql("""
                SELECT ABS(SUM(stock_value_difference)) AS total
                FROM `tabStock Ledger Entry`
                WHERE voucher_type = 'Stock Entry'
                  AND voucher_no = %(ste)s
                  AND item_code = %(item_code)s
                  AND stock_value_difference < 0
            """, {"ste": item.ste_reference, "item_code": item.kode_barang}, as_dict=True)

            if sle and sle[0].total:
                amount = sle[0].total

        result.append({
            "pengeluaran_barang": item.no_pb,
            "kode_vra": item.kendaraan,
            "no_coa": item.account,
            "amount": amount,
            "keterangan": item.item_name or item.kode_barang
        })

    return result


@frappe.whitelist()
def get_pengeluaran_barang_solar_bengkel(periode_dari, periode_sampai, company=None, unit=None):
    """
    Ambil Pengeluaran Barang Item dengan kode_barang = '50101001' (Solar) yang sub_unit = BENGKEL
    dan punya kendaraan (asset), hitung nilai per item dari Stock Ledger Entry berdasarkan
    STE reference + item_code. Return breakdown per kendaraan + COA.
    """
    company_filter = "AND pb.pt_pemilik_barang = %(company)s" if company else ""
    unit_filter = "AND pb.unit = %(unit)s" if unit else ""
    pb_items = frappe.db.sql("""
        SELECT
            pb.name AS no_pb,
            ste.name as ste_reference,
            pbi.kode_barang,
            pbi.item_name,
            pbi.kendaraan,
            pbi.account
        FROM `tabPengeluaran Barang` pb
        JOIN `tabPengeluaran Barang Item` pbi ON pbi.parent = pb.name
        JOIN `tabStock Entry` ste ON ste.pengeluaran_barang = pb.name AND ste.docstatus = 1
        WHERE pb.docstatus = 1
          AND pb.tanggal BETWEEN %(dari)s AND %(sampai)s
          AND (pbi.sub_unit = 'TRAKSI' or pbi.sub_unit = "BENGKEL")
          AND pbi.kendaraan != ''
          AND pbi.kendaraan IS NOT NULL
          AND pbi.kode_barang = '50101001'
          {company_filter}
          {unit_filter}
        ORDER BY pb.tanggal, pb.name, pbi.kendaraan;
    """.format(company_filter=company_filter, unit_filter=unit_filter), {"dari": periode_dari, "sampai": periode_sampai, "company": company, "unit": unit}, as_dict=True, debug=True)

    result = []
    for item in pb_items:
        amount = 0.0

        if item.ste_reference:
            sle = frappe.db.sql("""
                SELECT ABS(SUM(stock_value_difference)) AS total
                FROM `tabStock Ledger Entry`
                WHERE voucher_type = 'Stock Entry'
                  AND voucher_no = %(ste)s
                  AND item_code = %(item_code)s
                  AND stock_value_difference < 0
            """, {"ste": item.ste_reference, "item_code": item.kode_barang}, as_dict=True)

            if sle and sle[0].total:
                amount = sle[0].total

        result.append({
            "pengeluaran_barang": item.no_pb,
            "kode_vra": item.kendaraan,
            "no_coa": item.account,
            "amount": amount,
            "keterangan": item.item_name or item.kode_barang
        })

    return result


@frappe.whitelist()
def get_payslip_karyawan_bengkel(periode_dari, periode_sampai, company=None, unit=None):
    """
    Ambil GL Entry dari Payroll Entry yang designation-nya mengandung kata BENGKEL,
    filter account LIKE '4121001%', debit > 0, dalam periode.
    """
    company_filter = "AND pe.company = %(company)s" if company else ""
    unit_filter = "AND pe.unit = %(unit)s" if unit else ""
    rows = frappe.db.sql("""
        SELECT
            pe.name AS payroll_entry,
            pe.designation,
            gl.account,
            gl.debit AS amount,
            "ALOKASI GAJI KARYAWAN BENGKEL" as keterangan
        FROM `tabPayroll Entry` pe
        JOIN `tabGL Entry` gl
            ON gl.voucher_type = 'Payroll Entry'
            AND gl.voucher_no = pe.name
            AND gl.is_cancelled = 0
            AND gl.account LIKE '4121001%%'
            AND gl.debit > 0
        JOIN `tabDesignation` d ON d.name = pe.designation

        WHERE pe.docstatus = 1
          AND pe.start_date >= %(dari)s
          AND pe.end_date <= %(sampai)s
          AND UPPER(d.designation_name) LIKE '%%BENGKEL%%'
          {company_filter}
          {unit_filter}
        ORDER BY pe.start_date, pe.name
    """.format(company_filter=company_filter, unit_filter=unit_filter), {"dari": periode_dari, "sampai": periode_sampai, "company": company, "unit": unit}, as_dict=True)

    result = []
    for r in rows:
        result.append({
            "no_dokumen": r.payroll_entry,
            "no_coa": r.account,
            "amount": r.amount,
            "keterangan": r.keterangan
        })

    return result


@frappe.whitelist()
def get_gl_bkm_traksi_bengkel(periode_dari, periode_sampai, company=None, unit=None):
    """
    Ambil GL Entry asli dari semua Buku Kerja Mandor Traksi company/unit terkait dalam
    periode tsb. Tidak lagi bergantung pada daftar kendaraan Pengeluaran Barang Solar.
    """
    company_filter = "AND bkm.company = %(company)s" if company else ""
    unit_filter = "AND bkm.unit = %(unit)s" if unit else ""
    rows = frappe.db.sql("""
        SELECT
            bkm.name AS bkm_traksi,
            bkm.kendaraan,
            gl.account,
            gl.debit,
            gl.credit
        FROM `tabBuku Kerja Mandor Traksi` bkm
        JOIN `tabGL Entry` gl
            ON gl.voucher_type = 'Buku Kerja Mandor Traksi'
            AND gl.voucher_no = bkm.name
            AND gl.is_cancelled = 0
        WHERE bkm.docstatus = 1
          AND bkm.posting_date BETWEEN %(dari)s AND %(sampai)s
          {company_filter}
          {unit_filter}
        ORDER BY bkm.posting_date, bkm.name
    """.format(company_filter=company_filter, unit_filter=unit_filter), {
        "dari": periode_dari,
        "sampai": periode_sampai,
        "company": company,
        "unit": unit
    }, as_dict=True)

    result = []
    for r in rows:
        result.append({
            "bkm_traksi": r.bkm_traksi,
            "no_coa": r.account,
            "debit": r.debit or 0,
            "credit": r.credit or 0,
            "kode_vra": r.kendaraan,
            "keterangan": "ALOKASI VRA KE AKTIVITAS"
        })

    return result


@frappe.whitelist()
def get_closing_vra_bengkel(periode_dari, periode_sampai, company=None, unit=None):
    """
    Ambil semua BKM Traksi company/unit terkait dalam periode tsb (tidak lagi bergantung
    pada kendaraan yang muncul di Pengeluaran Barang Solar). Untuk tiap baris task -> kegiatan,
    ambil account dari items Kegiatan tsb (debit = grand_total BKM Traksi), dipasangkan
    dengan baris credit ke COA 4112099 - BIAYA KENDARAAN DIALOKASI (nilai sama).
    """
    company_filter = "AND bkm.company = %(company)s" if company else ""
    unit_filter = "AND bkm.unit = %(unit)s" if unit else ""
    bkm_list = frappe.db.sql("""
        SELECT bkm.name AS bkm_traksi, bkm.kendaraan, bkm.grand_total
        FROM `tabBuku Kerja Mandor Traksi` bkm
        WHERE bkm.docstatus = 1
          AND bkm.posting_date BETWEEN %(dari)s AND %(sampai)s
          {company_filter}
          {unit_filter}
        ORDER BY bkm.posting_date, bkm.name
    """.format(company_filter=company_filter, unit_filter=unit_filter), {
        "dari": periode_dari,
        "sampai": periode_sampai,
        "company": company,
        "unit": unit
    }, as_dict=True)

    coa_dialokasi = get_coa_biaya_kendaraan_dialokasi(company)

    result = []
    for bkm in bkm_list:
        kegiatan_list = frappe.get_all(
            "Detail BKM Traksi Kegiatan",
            filters={"parent": bkm.bkm_traksi, "parenttype": "Buku Kerja Mandor Traksi"},
            pluck="kegiatan"
        )

        accounts = set()
        for kegiatan in kegiatan_list:
            if not kegiatan:
                continue
            item_accounts = frappe.get_all(
                "Kegiatan Company",
                filters={"parent": kegiatan, "parenttype": "Kegiatan"},
                pluck="account"
            )
            accounts.update(a for a in item_accounts if a)

        for account in accounts:
            result.append({
                "bkm_traksi": bkm.bkm_traksi,
                "no_coa": account,
                "debit": bkm.grand_total or 0,
                "credit": 0,
                "kode_vra": bkm.kendaraan,
                "keterangan": "CLOSING VRA"
            })
            result.append({
                "bkm_traksi": bkm.bkm_traksi,
                "no_coa": coa_dialokasi,
                "debit": 0,
                "credit": bkm.grand_total or 0,
                "kode_vra": bkm.kendaraan,
                "keterangan": "CLOSING VRA"
            })

    return result


@frappe.whitelist()
def get_coa_biaya_kendaraan_dialokasi(company):
    """
    Ambil COA "4112099 - BIAYA KENDARAAN DIALOKASI" untuk company terkait.
    """
    return frappe.db.get_value("Account", {"company": company, "name": ["like", "4112099%"]}, "name")


@frappe.whitelist()
def get_payslip_operator_vra_bengkel(periode_dari, periode_sampai, company=None, unit=None):
    """
    Ambil GL Entry dari Payroll Entry yang designation-nya mengandung kata OPR (Operator VRA),
    filter account LIKE '4121001%', debit > 0, dalam periode.
    """
    company_filter = "AND pe.company = %(company)s" if company else ""
    unit_filter = "AND pe.unit = %(unit)s" if unit else ""
    rows = frappe.db.sql("""
        SELECT
            pe.name AS payroll_entry,
            pe.designation,
            gl.account,
            gl.debit AS amount,
            "ALOKASI GAJI OPERATOR VRA" as keterangan
        FROM `tabPayroll Entry` pe
        JOIN `tabGL Entry` gl
            ON gl.voucher_type = 'Payroll Entry'
            AND gl.voucher_no = pe.name
            AND gl.is_cancelled = 0
            AND gl.account LIKE '4121001%%'
            AND gl.debit > 0
        JOIN `tabDesignation` d ON d.name = pe.designation
        WHERE pe.docstatus = 1
          AND pe.start_date >= %(dari)s
          AND pe.end_date <= %(sampai)s
          AND UPPER(d.designation_name) LIKE '%%OPR%%'
          {company_filter}
          {unit_filter}
        ORDER BY pe.start_date, pe.name
    """.format(company_filter=company_filter, unit_filter=unit_filter), {"dari": periode_dari, "sampai": periode_sampai, "company": company, "unit": unit}, as_dict=True)

    result = []
    for r in rows:
        result.append({
            "no_dokumen": r.payroll_entry,
            "no_coa": r.account,
            "amount": r.amount,
            "keterangan": r.keterangan
        })

    return result


@frappe.whitelist()
def get_wkt_prb_bengkel(periode_dari, periode_sampai, company=None):
    """
    Ambil total waktu perbaikan (wkt_prb, satuan jam) per kendaraan (kd_kndr)
    dari Buku Kerja Mandor Bengkel dalam periode tsb. Dipakai sebagai basis
    alokasi gaji karyawan bengkel per kendaraan.
    """
    company_filter = "AND company = %(company)s" if company else ""
    rows = frappe.db.sql("""
        SELECT kd_kndr AS kendaraan, SUM(wkt_prb) AS total_wkt_prb
        FROM `tabBuku Kerja Mandor Bengkel`
        WHERE docstatus = 1
          AND posting_date BETWEEN %(dari)s AND %(sampai)s
          AND kd_kndr IS NOT NULL
          AND kd_kndr != ''
          {company_filter}
        GROUP BY kd_kndr
    """.format(company_filter=company_filter), {"dari": periode_dari, "sampai": periode_sampai, "company": company}, as_dict=True)

    return rows


@frappe.whitelist()
def get_coa_alokasi_gaji_bengkel(company):
    """
    Ambil COA untuk alokasi gaji bengkel dari STH Accounting Settings,
    child table sth_accounting_settings_alokasi_gaji_bengkel, filter by company.
    """
    result = frappe.db.sql("""
        SELECT account
        FROM `tabSTH Accounting Settings Alokasi Gaji Bengkel`
        WHERE company = %(company)s
        LIMIT 1
    """, {"company": company}, as_dict=True)

    return result[0].account if result else None


@frappe.whitelist()
def get_coa_reparasi_bengkel(company):
    """
    Ambil COA Reparasi Bengkel dari STH Accounting Settings,
    child table sth_accounting_settings_reparasi_bengkel_account, filter by company.
    """
    result = frappe.db.sql("""
        SELECT account
        FROM `tabSTH Accounting Settings Reparasi Bengkel Account`
        WHERE company = %(company)s
        LIMIT 1
    """, {"company": company}, as_dict=True)

    return result[0].account if result else None


@frappe.whitelist()
def get_coa_biaya_bengkel_dialokasi(company):
    """
    Ambil COA Biaya Bengkel Dialokasi dari STH Accounting Settings,
    child table sth_accounting_settings_biaya_bengkel_dialokasi, filter by company.
    """
    result = frappe.db.sql("""
        SELECT account
        FROM `tabSTH Accounting Settings Biaya Bengkel Dialokasi`
        WHERE company = %(company)s
        LIMIT 1
    """, {"company": company}, as_dict=True)

    return result[0].account if result else None


def build_and_submit_costing_bengkel(company, unit, periode_dari, periode_sampai):
    """
    Buat dan submit Costing Bengkel secara otomatis untuk company/unit/periode tertentu.
    Mereplikasi logika "Ambil Data" (costing_bengkel.js) di sisi server, dipakai saat
    Accounting Period disubmit lewat workflow.
    """
    cb = frappe.new_doc("Costing Bengkel")
    cb.company = company
    cb.unit = unit
    cb.periode_dari = periode_dari
    cb.periode_sampai = periode_sampai

    pb_rows = get_pengeluaran_barang_bengkel(periode_dari, periode_sampai, company, unit)
    pb_solar_rows = get_pengeluaran_barang_solar_bengkel(periode_dari, periode_sampai, company, unit)
    payslip_rows = get_payslip_karyawan_bengkel(periode_dari, periode_sampai, company, unit)
    payslip_opr_rows = get_payslip_operator_vra_bengkel(periode_dari, periode_sampai, company, unit)
    coa_alokasi = get_coa_alokasi_gaji_bengkel(company)
    coa_reparasi = get_coa_reparasi_bengkel(company)
    coa_dialokasi = get_coa_biaya_bengkel_dialokasi(company)

    for row in pb_rows:
        cb.append("costing_bengkel_pengeluaran_barang", {
            "pengeluaran_barang": row["pengeluaran_barang"],
            "kode_vra": row["kode_vra"],
            "no_coa": row["no_coa"],
            "amount": row["amount"],
            "keterangan": row["keterangan"],
        })

    for row in pb_solar_rows:
        cb.append("costing_bengkel_pengeluaran_barang_solar", {
            "pengeluaran_barang": row["pengeluaran_barang"],
            "kode_vra": row["kode_vra"],
            "no_coa": row["no_coa"],
            "amount": row["amount"],
            "keterangan": row["keterangan"],
        })

    for row in payslip_rows:
        cb.append("costing_bengkel_payslip_karyawan_bengkel", {
            "payroll_no": row["no_dokumen"],
            "no_coa": row["no_coa"],
            "amount": row["amount"],
            "keterangan": row["keterangan"],
        })

    wkt_prb_rows = get_wkt_prb_bengkel(periode_dari, periode_sampai, company)
    total_payslip = sum(r["amount"] or 0 for r in payslip_rows)
    total_wkt_prb = sum(r.total_wkt_prb or 0 for r in wkt_prb_rows)
    rate_per_jam = (total_payslip / total_wkt_prb) if total_wkt_prb else 0

    alokasi_gaji_map = {r.kendaraan: (r.total_wkt_prb or 0) * rate_per_jam for r in wkt_prb_rows}

    for kendaraan, amount_per_kendaraan in alokasi_gaji_map.items():
        cb.append("costing_bengkel_alokasi_gaji_karyawan_bengkel", {
            "kode_vra": kendaraan,
            "no_coa": coa_alokasi,
            "amount": amount_per_kendaraan,
            "keterangan": "ALOKASI GAJI KARYAWAN BENGKEL",
        })

    unique_vra = list(dict.fromkeys(
        list(alokasi_gaji_map.keys()) + [r["kode_vra"] for r in pb_rows if r.get("kode_vra")]
    ))

    for kendaraan in unique_vra:
        total_pb_kendaraan = sum(r["amount"] or 0 for r in pb_rows if r.get("kode_vra") == kendaraan)
        amount_per_kendaraan = alokasi_gaji_map.get(kendaraan, 0)
        closing_amount = total_pb_kendaraan + amount_per_kendaraan

        cb.append("costing_bengkel_closing_bengkel", {
            "no_coa": coa_reparasi,
            "debit": closing_amount,
            "credit": 0,
            "kode_vra": kendaraan,
            "keterangan": "ALOKASI BIAYA BENGKEL KE VRA {0}".format(kendaraan),
        })
        cb.append("costing_bengkel_closing_bengkel", {
            "no_coa": coa_dialokasi,
            "debit": 0,
            "credit": closing_amount,
            "kode_vra": kendaraan,
            "keterangan": "ALOKASI BIAYA BENGKEL KE VRA {0}".format(kendaraan),
        })

    for row in payslip_opr_rows:
        cb.append("costing_bengkel_payslip_operator_vra", {
            "payroll_no": row["no_dokumen"],
            "no_coa": row["no_coa"],
            "amount": row["amount"],
            "keterangan": row["keterangan"],
        })

    unique_vra_solar = list(dict.fromkeys(r["kode_vra"] for r in pb_solar_rows if r.get("kode_vra")))
    total_payslip_opr = sum(r["amount"] or 0 for r in payslip_opr_rows)
    jumlah_kendaraan_solar = len(unique_vra_solar)
    amount_per_kendaraan_opr = (total_payslip_opr / jumlah_kendaraan_solar) if jumlah_kendaraan_solar else 0

    for kendaraan in unique_vra_solar:
        cb.append("costing_bengkel_alokasi_gaji_operator_vra", {
            "kode_vra": kendaraan,
            "no_coa": coa_alokasi,
            "amount": amount_per_kendaraan_opr,
            "keterangan": "ALOKASI GAJI OPERATOR VRA",
        })

    gl_bkm_traksi_rows = get_gl_bkm_traksi_bengkel(periode_dari, periode_sampai, company, unit)
    for row in gl_bkm_traksi_rows:
        cb.append("costing_bengkel_gl_bkm_traksi", {
            "bkm_traksi": row["bkm_traksi"],
            "no_coa": row["no_coa"],
            "debit": row["debit"],
            "credit": row["credit"],
            "kode_vra": row["kode_vra"],
            "keterangan": row["keterangan"],
        })

    closing_vra_rows = get_closing_vra_bengkel(periode_dari, periode_sampai, company, unit)
    for row in closing_vra_rows:
        cb.append("costing_bengkel_closing_vra", {
            "bkm_traksi": row["bkm_traksi"],
            "no_coa": row["no_coa"],
            "debit": row["debit"],
            "credit": row["credit"],
            "kode_vra": row["kode_vra"],
            "keterangan": row["keterangan"],
        })
        
    cb.insert(ignore_permissions=True)
    # cb.submit()

    return cb.name


@frappe.whitelist()
def get_salary_slip_bengkel(periode_dari, periode_sampai, unit=None):
    """
    Ambil Salary Slip karyawan divisi BENGKEL yang sudah submit dalam periode.
    Menggunakan field department pada Salary Slip dan Employee.
    """
    unit_filter = "AND e.unit = %(unit)s" if unit else ""
    salary_list = frappe.db.sql("""
        SELECT ss.name, ss.net_pay
        FROM `tabSalary Slip` ss
        WHERE ss.docstatus = 1
          AND ss.start_date >= %(dari)s
          AND ss.end_date <= %(sampai)s
          AND EXISTS (
              SELECT 1 FROM `tabEmployee` e
              WHERE e.name = ss.employee
                AND UPPER(e.department) LIKE '%%BENGKEL%%'
                {unit_filter}
          )
        ORDER BY ss.start_date, ss.name
    """.format(unit_filter=unit_filter), {"dari": periode_dari, "sampai": periode_sampai, "unit": unit}, as_dict=True)

    result = []
    for ss in salary_list:
        result.append({
            "no_dokumen": ss.name,
            "total": ss.net_pay or 0.0
        })

    return result
