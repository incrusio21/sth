# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

TANPA_STASIUN = "TANPA STASIUN"


class CostingMill(Document):

    def before_save(self):
        self.hitung_rekap_stasiun()
        self.hitung_total()

    def hitung_total(self):
        self.total_gaji_karyawan = sum(d.amount or 0 for d in self.costing_mill_gaji_karyawan)
        self.total_pengeluaran_barang = sum(d.amount or 0 for d in self.costing_mill_pengeluaran_barang)
        self.total_bkm = sum(d.amount or 0 for d in self.costing_mill_bkm)
        self.grand_total = (
            (self.total_gaji_karyawan or 0)
            + (self.total_pengeluaran_barang or 0)
            + (self.total_bkm or 0)
        )

    def hitung_rekap_stasiun(self):
        """
        Tabel D — rekap per stasiun dari tabel A + B + C yang sudah terisi di form.
        Selalu dihitung ulang supaya tetap konsisten walau baris A/B/C diedit manual.
        """
        rekap = {}

        def add(stasiun, key, amount):
            row = rekap.setdefault(stasiun or "", {
                "total_gaji_karyawan": 0,
                "total_pengeluaran_barang": 0,
                "total_bkm": 0,
            })
            row[key] += amount or 0

        for d in self.costing_mill_gaji_karyawan:
            add(d.stasiun, "total_gaji_karyawan", d.amount)
        for d in self.costing_mill_pengeluaran_barang:
            add(d.stasiun, "total_pengeluaran_barang", d.amount)
        for d in self.costing_mill_bkm:
            add(d.stasiun, "total_bkm", d.amount)

        self.set("costing_mill_stasiun", [])
        for stasiun in sorted(rekap.keys()):
            nilai = rekap[stasiun]
            self.append("costing_mill_stasiun", {
                "stasiun": stasiun or None,
                "nama_stasiun": get_nama_stasiun(stasiun) if stasiun else TANPA_STASIUN,
                "cost_center": get_cost_center_stasiun(stasiun, self.unit) if stasiun else None,
                "no_coa": get_coa_stasiun(stasiun, self.company) if stasiun else None,
                "total_gaji_karyawan": nilai["total_gaji_karyawan"],
                "total_pengeluaran_barang": nilai["total_pengeluaran_barang"],
                "total_bkm": nilai["total_bkm"],
                "total": nilai["total_gaji_karyawan"] + nilai["total_pengeluaran_barang"] + nilai["total_bkm"],
            })


# ---------------------------------------------------------------------------
# Helper master data stasiun
# ---------------------------------------------------------------------------

def get_nama_stasiun(stasiun):
    return frappe.db.get_value("Station Master", stasiun, "machine_name") if stasiun else None


@frappe.whitelist()
def get_coa_stasiun(stasiun, company=None):
    """
    COA stasiun diambil dari child table Station Procurement Settings
    di Station Master, dipilih berdasarkan company.
    """
    if not stasiun or not company:
        return None

    return frappe.db.get_value(
        "Station Procurement Settings",
        {"parent": stasiun, "parenttype": "Station Master", "company": company},
        "account",
    )


@frappe.whitelist()
def get_cost_center_stasiun(stasiun, unit=None):
    """
    Cost Center stasiun diambil dari child table Detail Station Master
    di Station Master, dipilih berdasarkan unit.
    """
    if not stasiun:
        return None

    filters = {"parent": stasiun, "parenttype": "Station Master"}
    if unit:
        filters["unit"] = unit

    return frappe.db.get_value("Detail Station Master", filters, "cost_center")


def _unit_mill_list(company=None, unit=None):
    """Daftar Unit yang field mill-nya tercentang, opsional dipersempit ke satu unit."""
    filters = {"mill": 1}
    if company:
        filters["company"] = company
    if unit:
        filters["name"] = unit

    return [u.name for u in frappe.get_all("Unit", filters=filters, fields=["name"])]


# ---------------------------------------------------------------------------
# A. Gaji Karyawan Mill
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_gaji_karyawan_mill(periode_dari, periode_sampai, company=None, unit=None):
    """
    Tabel A — Salary Slip karyawan yang unit-nya punya centang Mill,
    dipecah per stasiun karyawan (Employee.stasiun).
    Nilai memakai net_pay Salary Slip.
    """
    unit_list = _unit_mill_list(company, unit)
    if not unit_list:
        return []

    company_filter = "AND ss.company = %(company)s" if company else ""
    rows = frappe.db.sql("""
        SELECT
            ss.name AS salary_slip,
            ss.employee,
            ss.employee_name,
            e.stasiun,
            e.coa_stasiun,
            ss.net_pay AS amount
        FROM `tabSalary Slip` ss
        JOIN `tabEmployee` e ON e.name = ss.employee
        WHERE ss.docstatus = 1
          AND ss.start_date >= %(dari)s
          AND ss.end_date <= %(sampai)s
          AND COALESCE(NULLIF(ss.unit, ''), e.unit) IN %(unit_list)s
          {company_filter}
        ORDER BY e.stasiun, ss.start_date, ss.name
    """.format(company_filter=company_filter), {
        "dari": periode_dari, "sampai": periode_sampai,
        "unit_list": tuple(unit_list), "company": company,
    }, as_dict=True)

    result = []
    for r in rows:
        result.append({
            "salary_slip": r.salary_slip,
            "employee": r.employee,
            "employee_name": r.employee_name,
            "stasiun": r.stasiun,
            "no_coa": r.coa_stasiun or get_coa_stasiun(r.stasiun, company),
            "amount": r.amount or 0,
            "keterangan": "GAJI KARYAWAN MILL",
        })

    return result


# ---------------------------------------------------------------------------
# B. Pengeluaran Barang Mill
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_pengeluaran_barang_mill(periode_dari, periode_sampai, company=None, unit=None):
    """
    Tabel B — Pengeluaran Barang Item yang divisinya (sub_unit) punya centang Mill,
    dipecah per stasiun item (Pengeluaran Barang Item.stasiun).
    Nilai diambil dari Stock Ledger Entry milik Stock Entry pasangannya.
    """
    company_filter = "AND pb.pt_pemilik_barang = %(company)s" if company else ""
    unit_filter = "AND pb.unit = %(unit)s" if unit else ""

    pb_items = frappe.db.sql("""
        SELECT
            pb.name AS no_pb,
            ste.name AS ste_reference,
            pbi.kode_barang,
            pbi.item_name,
            pbi.sub_unit,
            pbi.stasiun,
            pbi.account
        FROM `tabPengeluaran Barang` pb
        JOIN `tabPengeluaran Barang Item` pbi ON pbi.parent = pb.name
        JOIN `tabStock Entry` ste ON ste.pengeluaran_barang = pb.name AND ste.docstatus = 1
        JOIN `tabDivisi` dv ON dv.name = pbi.sub_unit AND dv.mill = 1
        WHERE pb.docstatus = 1
          AND pb.tanggal BETWEEN %(dari)s AND %(sampai)s
          {company_filter}
          {unit_filter}
        ORDER BY pbi.stasiun, pb.tanggal, pb.name
    """.format(company_filter=company_filter, unit_filter=unit_filter), {
        "dari": periode_dari, "sampai": periode_sampai, "company": company, "unit": unit,
    }, as_dict=True)

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
            "sub_unit": item.sub_unit,
            "stasiun": item.stasiun,
            "kode_barang": item.kode_barang,
            "no_coa": item.account or get_coa_stasiun(item.stasiun, company),
            "amount": amount,
            "keterangan": item.item_name or item.kode_barang,
        })

    return result


# ---------------------------------------------------------------------------
# C. BKM Bengkel & BKM Traksi
# ---------------------------------------------------------------------------

def _get_item_valuation_rate(item_code, posting_date):
    """
    Harga satuan sparepart BKM Bengkel: valuation_rate terakhir dari Stock Ledger Entry
    sampai dengan posting_date, fallback ke valuation_rate di master Item.
    """
    if not item_code:
        return 0

    rate = frappe.db.sql("""
        SELECT valuation_rate
        FROM `tabStock Ledger Entry`
        WHERE item_code = %(item_code)s
          AND is_cancelled = 0
          AND posting_date <= %(posting_date)s
          AND valuation_rate > 0
        ORDER BY posting_date DESC, posting_time DESC, creation DESC
        LIMIT 1
    """, {"item_code": item_code, "posting_date": posting_date})

    if rate and rate[0][0]:
        return rate[0][0]

    return frappe.db.get_value("Item", item_code, "valuation_rate") or 0


def _get_bkm_bengkel_rows(periode_dari, periode_sampai, company, unit_list):
    """
    BKM Bengkel tidak punya field unit/stasiun/nilai sendiri, jadi:
      - unit  : lewat Data Bengkel (field bkl) yang unit-nya centang Mill
      - nilai : total pemakaian sparepart (Detail Item Bengkel) x valuation rate
      - stasiun: dari Employee.stasiun karyawan di tabel Hasil Kerja,
                 kalau lebih dari satu stasiun nilainya dibagi rata.
    """
    company_filter = "AND bkm.company = %(company)s" if company else ""
    bkm_rows = frappe.db.sql("""
        SELECT bkm.name, bkm.posting_date
        FROM `tabBuku Kerja Mandor Bengkel` bkm
        JOIN `tabData Bengkel` bkl ON bkl.name = bkm.bkl
        WHERE bkm.docstatus = 1
          AND bkm.posting_date BETWEEN %(dari)s AND %(sampai)s
          AND bkl.unit IN %(unit_list)s
          {company_filter}
        ORDER BY bkm.posting_date, bkm.name
    """.format(company_filter=company_filter), {
        "dari": periode_dari, "sampai": periode_sampai,
        "unit_list": tuple(unit_list), "company": company,
    }, as_dict=True)

    if not bkm_rows:
        return []

    bkm_names = [r.name for r in bkm_rows]

    items = frappe.get_all(
        "Detail Item Bengkel",
        filters={"parent": ["in", bkm_names], "parenttype": "Buku Kerja Mandor Bengkel"},
        fields=["parent", "item_code", "qty"],
    )
    items_by_bkm = {}
    for it in items:
        items_by_bkm.setdefault(it.parent, []).append(it)

    mekanik = frappe.get_all(
        "Detail Transaksi Employee",
        filters={"parent": ["in", bkm_names], "parenttype": "Buku Kerja Mandor Bengkel"},
        fields=["parent", "employee"],
    )
    employees = list({m.employee for m in mekanik if m.employee})
    stasiun_by_employee = {
        e.name: e.stasiun
        for e in frappe.get_all("Employee", filters={"name": ["in", employees]}, fields=["name", "stasiun"])
    } if employees else {}

    stasiun_by_bkm = {}
    for m in mekanik:
        stasiun = stasiun_by_employee.get(m.employee)
        if stasiun:
            stasiun_by_bkm.setdefault(m.parent, [])
            if stasiun not in stasiun_by_bkm[m.parent]:
                stasiun_by_bkm[m.parent].append(stasiun)

    result = []
    for bkm in bkm_rows:
        stasiun_list = stasiun_by_bkm.get(bkm.name) or [None]
        pembagi = len(stasiun_list)

        for it in items_by_bkm.get(bkm.name, []):
            nilai = (it.qty or 0) * _get_item_valuation_rate(it.item_code, bkm.posting_date)
            if not nilai:
                continue

            for stasiun in stasiun_list:
                result.append({
                    "sumber": "BKM Bengkel",
                    "reference_doctype": "Buku Kerja Mandor Bengkel",
                    "no_dokumen": bkm.name,
                    "stasiun": stasiun,
                    "no_coa": get_coa_stasiun(stasiun, company),
                    "amount": nilai / pembagi,
                    "keterangan": "SPAREPART BKM BENGKEL {0}".format(it.item_code),
                })

    return result


def _get_bkm_traksi_rows(periode_dari, periode_sampai, company, unit_list):
    """
    BKM Traksi yang unit-nya centang Mill. Nilai memakai grand_total (upah + premi),
    fallback ke hasil_kerja_amount. Stasiun diambil dari header BKM Traksi; kalau
    header kosong, nilainya dipecah proporsional terhadap amount kegiatan (task)
    yang punya stasiun.
    """
    company_filter = "AND bkm.company = %(company)s" if company else ""
    bkm_rows = frappe.db.sql("""
        SELECT bkm.name, bkm.stasiun, bkm.grand_total, bkm.hasil_kerja_amount
        FROM `tabBuku Kerja Mandor Traksi` bkm
        WHERE bkm.docstatus = 1
          AND bkm.posting_date BETWEEN %(dari)s AND %(sampai)s
          AND bkm.unit IN %(unit_list)s
          {company_filter}
        ORDER BY bkm.posting_date, bkm.name
    """.format(company_filter=company_filter), {
        "dari": periode_dari, "sampai": periode_sampai,
        "unit_list": tuple(unit_list), "company": company,
    }, as_dict=True)

    if not bkm_rows:
        return []

    tanpa_stasiun = [r.name for r in bkm_rows if not r.stasiun]
    task_by_bkm = {}
    if tanpa_stasiun:
        for t in frappe.get_all(
            "Detail BKM Traksi Kegiatan",
            filters={"parent": ["in", tanpa_stasiun], "parenttype": "Buku Kerja Mandor Traksi"},
            fields=["parent", "stasiun", "amount"],
        ):
            if t.stasiun:
                task_by_bkm.setdefault(t.parent, {})
                task_by_bkm[t.parent][t.stasiun] = task_by_bkm[t.parent].get(t.stasiun, 0) + (t.amount or 0)

    result = []
    for bkm in bkm_rows:
        nilai = bkm.grand_total or bkm.hasil_kerja_amount or 0
        if not nilai:
            continue

        if bkm.stasiun:
            porsi = {bkm.stasiun: nilai}
        else:
            per_stasiun = task_by_bkm.get(bkm.name) or {}
            total_task = sum(per_stasiun.values())
            if total_task:
                porsi = {st: nilai * (amt / total_task) for st, amt in per_stasiun.items()}
            else:
                porsi = {None: nilai}

        for stasiun, amount in porsi.items():
            result.append({
                "sumber": "BKM Traksi",
                "reference_doctype": "Buku Kerja Mandor Traksi",
                "no_dokumen": bkm.name,
                "stasiun": stasiun,
                "no_coa": get_coa_stasiun(stasiun, company),
                "amount": amount,
                "keterangan": "UPAH BKM TRAKSI",
            })

    return result


@frappe.whitelist()
def get_bkm_mill(periode_dari, periode_sampai, company=None, unit=None):
    """
    Tabel C — gabungan BKM Bengkel dan BKM Traksi yang unit-nya centang Mill,
    dipecah per stasiun.
    """
    unit_list = _unit_mill_list(company, unit)
    if not unit_list:
        return []

    return (
        _get_bkm_bengkel_rows(periode_dari, periode_sampai, company, unit_list)
        + _get_bkm_traksi_rows(periode_dari, periode_sampai, company, unit_list)
    )


# ---------------------------------------------------------------------------
# D. Rekap per stasiun + pengambilan data sekaligus
# ---------------------------------------------------------------------------

def build_rekap_stasiun(gaji_rows, pb_rows, bkm_rows, company=None, unit=None):
    """
    Tabel D — total A + B + C per stasiun. Dipakai bersama oleh get_costing_mill_data
    dan build_costing_mill supaya angkanya konsisten.
    """
    rekap = {}

    def add(stasiun, key, amount):
        row = rekap.setdefault(stasiun or "", {
            "total_gaji_karyawan": 0,
            "total_pengeluaran_barang": 0,
            "total_bkm": 0,
        })
        row[key] += amount or 0

    for r in gaji_rows:
        add(r.get("stasiun"), "total_gaji_karyawan", r.get("amount"))
    for r in pb_rows:
        add(r.get("stasiun"), "total_pengeluaran_barang", r.get("amount"))
    for r in bkm_rows:
        add(r.get("stasiun"), "total_bkm", r.get("amount"))

    result = []
    for stasiun in sorted(rekap.keys()):
        nilai = rekap[stasiun]
        result.append({
            "stasiun": stasiun or None,
            "nama_stasiun": get_nama_stasiun(stasiun) if stasiun else TANPA_STASIUN,
            "cost_center": get_cost_center_stasiun(stasiun, unit) if stasiun else None,
            "no_coa": get_coa_stasiun(stasiun, company) if stasiun else None,
            "total_gaji_karyawan": nilai["total_gaji_karyawan"],
            "total_pengeluaran_barang": nilai["total_pengeluaran_barang"],
            "total_bkm": nilai["total_bkm"],
            "total": nilai["total_gaji_karyawan"] + nilai["total_pengeluaran_barang"] + nilai["total_bkm"],
        })

    return result


@frappe.whitelist()
def get_costing_mill_data(periode_dari, periode_sampai, company=None, unit=None):
    """
    Satu panggilan untuk tombol "Ambil Data": mengembalikan tabel A, B, C dan rekap D.
    """
    gaji_rows = get_gaji_karyawan_mill(periode_dari, periode_sampai, company, unit)
    pb_rows = get_pengeluaran_barang_mill(periode_dari, periode_sampai, company, unit)
    bkm_rows = get_bkm_mill(periode_dari, periode_sampai, company, unit)

    return {
        "gaji_karyawan": gaji_rows,
        "pengeluaran_barang": pb_rows,
        "bkm": bkm_rows,
        "stasiun": build_rekap_stasiun(gaji_rows, pb_rows, bkm_rows, company, unit),
    }


def build_costing_mill(company, unit, periode_dari, periode_sampai, submit=False):
    """
    Buat Costing Mill secara otomatis untuk company/unit/periode tertentu.
    Mereplikasi logika tombol "Ambil Data" di sisi server.
    """
    data = get_costing_mill_data(periode_dari, periode_sampai, company, unit)

    cm = frappe.new_doc("Costing Mill")
    cm.company = company
    cm.unit = unit
    cm.periode_dari = periode_dari
    cm.periode_sampai = periode_sampai

    for row in data["gaji_karyawan"]:
        cm.append("costing_mill_gaji_karyawan", row)
    for row in data["pengeluaran_barang"]:
        cm.append("costing_mill_pengeluaran_barang", row)
    for row in data["bkm"]:
        cm.append("costing_mill_bkm", row)

    cm.insert(ignore_permissions=True)

    if submit:
        cm.submit()

    return cm.name
