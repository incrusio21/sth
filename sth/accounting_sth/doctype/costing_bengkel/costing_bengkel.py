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
        self.total_kegiatan_bkm_traksi = sum(d.debit or 0 for d in self.costing_bengkel_kegiatan_bkm_traksi)
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
    Alokasi gaji operator VRA per kendaraan — 2 baris per kendaraan:
      Debit  → 4112001 (Gaji Pengemudi)
      Credit → 4121001 (Beban Gaji Operator)
    """
    coa_debit = get_coa_gaji_pengemudi(company)
    coa_credit = get_coa_beban_gaji_operator(company)
    alokasi_map = _compute_alokasi_gaji_opr_per_kendaraan(periode_dari, periode_sampai, company, unit)

    result = []
    for kendaraan, amount in alokasi_map.items():
        if amount:
            result.append({
                "no_coa": coa_debit,
                "debit": amount,
                "credit": 0,
                "kode_vra": kendaraan,
                "keterangan": "ALOKASI GAJI OPERATOR VRA"
            })
            result.append({
                "no_coa": coa_credit,
                "debit": 0,
                "credit": amount,
                "kode_vra": kendaraan,
                "keterangan": "ALOKASI GAJI OPERATOR VRA"
            })
    return result


def _get_closing_bengkel_rows(periode_dari, periode_sampai, company, unit):
    """
    Hitung ulang baris Closing Bengkel (2 baris per kendaraan: debit ke COA Reparasi,
    credit ke COA Biaya Bengkel Dialokasi). Dipakai bersama oleh build_and_submit,
    get_closing_vra_bengkel, dan get_cost_per_kmhm_bengkel supaya angkanya konsisten.
    """
    pb_rows = get_pengeluaran_barang_bengkel(periode_dari, periode_sampai, company, unit)
    payslip_rows = get_payslip_karyawan_bengkel(periode_dari, periode_sampai, company, unit)
    wkt_prb_rows = get_wkt_prb_bengkel(periode_dari, periode_sampai, company)
    total_payslip = sum(r["amount"] or 0 for r in payslip_rows)
    total_wkt_prb = sum(r.total_wkt_prb or 0 for r in wkt_prb_rows)
    rate_per_jam = (total_payslip / total_wkt_prb) if total_wkt_prb else 0
    alokasi_gaji_map = {r.kendaraan: (r.total_wkt_prb or 0) * rate_per_jam for r in wkt_prb_rows}
    unique_vra_bengkel = list(dict.fromkeys(
        list(alokasi_gaji_map.keys()) + [r["kode_vra"] for r in pb_rows if r.get("kode_vra")]
    ))
    coa_reparasi = get_coa_reparasi_bengkel(company)
    coa_biaya_bengkel_dialokasi = get_coa_biaya_bengkel_dialokasi(company)

    result = []
    for kend in unique_vra_bengkel:
        total_pb = sum(r["amount"] or 0 for r in pb_rows if r.get("kode_vra") == kend)
        closing_amount = total_pb + alokasi_gaji_map.get(kend, 0)
        keterangan = "ALOKASI BIAYA BENGKEL KE VRA {0}".format(kend)
        result.append({"no_coa": coa_reparasi, "debit": closing_amount, "credit": 0, "kode_vra": kend, "keterangan": keterangan})
        result.append({"no_coa": coa_biaya_bengkel_dialokasi, "debit": 0, "credit": closing_amount, "kode_vra": kend, "keterangan": keterangan})

    return result


@frappe.whitelist()
def get_total_kmhm_bengkel(periode_dari, periode_sampai, company=None, unit=None):
    """
    Total KM/HM per kendaraan dari Buku Kerja Mandor Traksi + Buku Kerja Mandor Bengkel
    dalam periode tsb. Dipakai sebagai basis Total Cost Per KM/HM.
    """
    company_filter = "AND company = %(company)s" if company else ""
    unit_filter = "AND unit = %(unit)s" if unit else ""

    traksi_rows = frappe.db.sql("""
        SELECT kendaraan, SUM(kmhm_akhir - kmhm_awal) AS total_kmhm
        FROM `tabBuku Kerja Mandor Traksi`
        WHERE docstatus = 1
          AND posting_date BETWEEN %(dari)s AND %(sampai)s
          AND kendaraan IS NOT NULL AND kendaraan != ''
          {company_filter}
          {unit_filter}
        GROUP BY kendaraan
    """.format(company_filter=company_filter, unit_filter=unit_filter), {
        "dari": periode_dari, "sampai": periode_sampai, "company": company, "unit": unit
    }, as_dict=True)

    bengkel_rows = frappe.db.sql("""
        SELECT kd_kndr AS kendaraan, SUM(kmhm_akhir - kmhm_awal) AS total_kmhm
        FROM `tabBuku Kerja Mandor Bengkel`
        WHERE docstatus = 1
          AND posting_date BETWEEN %(dari)s AND %(sampai)s
          AND kd_kndr IS NOT NULL AND kd_kndr != ''
          {company_filter}
        GROUP BY kd_kndr
    """.format(company_filter=company_filter), {
        "dari": periode_dari, "sampai": periode_sampai, "company": company
    }, as_dict=True)

    total_map = {}
    for r in list(traksi_rows) + list(bengkel_rows):
        if r.kendaraan:
            total_map[r.kendaraan] = total_map.get(r.kendaraan, 0) + (r.total_kmhm or 0)

    return total_map


@frappe.whitelist()
def get_cost_per_kmhm_bengkel(periode_dari, periode_sampai, company=None, unit=None):
    """
    Total Cost Per KM/HM per kendaraan dihitung dari tiga sumber biaya:
      1. Pengeluaran Barang Solar  → bahan bakar per kendaraan
      2. Alokasi Gaji Operator VRA → gaji operator per kendaraan
      3. Closing Bengkel (credit)  → biaya suku cadang + gaji karyawan bengkel per kendaraan
    Tidak menggunakan get_closing_vra_bengkel untuk menghindari circular dependency
    (get_closing_vra_bengkel → get_kegiatan_bkm_traksi_bengkel → fungsi ini).
    """
    biaya_map = {}

    for r in get_pengeluaran_barang_solar_bengkel(periode_dari, periode_sampai, company, unit):
        kend = r.get("kode_vra")
        if kend:
            biaya_map[kend] = biaya_map.get(kend, 0) + (r.get("amount") or 0)

    for kend, amount in _compute_alokasi_gaji_opr_per_kendaraan(periode_dari, periode_sampai, company, unit).items():
        biaya_map[kend] = biaya_map.get(kend, 0) + (amount or 0)

    for r in _get_closing_bengkel_rows(periode_dari, periode_sampai, company, unit):
        if r.get("credit"):
            kend = r.get("kode_vra")
            if kend:
                biaya_map[kend] = biaya_map.get(kend, 0) + (r.get("credit") or 0)

    total_kmhm_map = get_total_kmhm_bengkel(periode_dari, periode_sampai, company, unit)

    return {
        kend: (biaya / total_kmhm_map[kend]) if total_kmhm_map.get(kend) else 0
        for kend, biaya in biaya_map.items()
    }


@frappe.whitelist()
def get_kegiatan_bkm_traksi_bengkel(bkm_traksi_list, periode_dari, periode_sampai, company=None, unit=None):
    """
    Untuk tiap task (Detail BKM Traksi Kegiatan) pada BKM Traksi yang sudah terambil di
    costing_bengkel_gl_bkm_traksi: debit = (kmhm_akhir - kmhm_awal) * Total Cost Per KM/HM
    kendaraan tsb (lihat get_cost_per_kmhm_bengkel), account debit dari Kegiatan Company
    yang company-nya sama dengan Costing Bengkel. Credit dipasangkan ke COA 4112099
    - BIAYA KENDARAAN DIALOKASI (nilai sama).
    """
    if isinstance(bkm_traksi_list, str):
        bkm_traksi_list = frappe.parse_json(bkm_traksi_list)

    if not bkm_traksi_list:
        return []

    coa_dialokasi = get_coa_biaya_kendaraan_dialokasi(company)
    cost_per_kmhm = get_cost_per_kmhm_bengkel(periode_dari, periode_sampai, company, unit)

    task_rows = frappe.get_all(
        "Detail BKM Traksi Kegiatan",
        filters={"parent": ["in", bkm_traksi_list], "parenttype": "Buku Kerja Mandor Traksi"},
        fields=["parent", "kegiatan", "kmhm_awal", "kmhm_akhir"],
    )

    kendaraan_map = {
        r.name: r.kendaraan
        for r in frappe.get_all(
            "Buku Kerja Mandor Traksi",
            filters={"name": ["in", bkm_traksi_list]},
            fields=["name", "kendaraan"],
        )
    }
    print(kendaraan_map)
    print(task_rows)
    result = []
    for t in task_rows:
        if not t.kegiatan:
            continue

        kode_vra = kendaraan_map.get(t.parent)
        rate = cost_per_kmhm.get(kode_vra, 0)
        jarak = (t.kmhm_akhir or 0) - (t.kmhm_awal or 0)
        amount = jarak * rate

        if not amount:
            continue

        account = frappe.db.get_value(
            "Kegiatan Company",
            {"parent": t.kegiatan, "parenttype": "Kegiatan", "company": company},
            "account",
        )

        if not account:
            continue

        result.append({
            "bkm_traksi": t.parent,
            "no_coa": account,
            "debit": amount,
            "credit": 0,
            "kode_vra": kode_vra,
            "keterangan": "ALOKASI VRA KE AKTIVITAS"
        })
        result.append({
            "bkm_traksi": t.parent,
            "no_coa": coa_dialokasi,
            "debit": 0,
            "credit": amount,
            "kode_vra": kode_vra,
            "keterangan": "ALOKASI VRA KE AKTIVITAS"
        })

    return result


def _get_closing_vra_netting_rows(periode_dari, periode_sampai, company, unit):
    """
    Hitung netting Closing VRA per kendaraan (tanpa kegiatan, untuk menghindari circular
    dependency dengan get_cost_per_kmhm_bengkel).
    Debit: Alokasi Gaji OPR (4112001) + Biaya Bengkel Dialokasi (credit closing bengkel).
    Credit: 4112099 per kendaraan.
    """
    debit_map = {}

    def add_debit(kend, coa, amount):
        if kend and coa and amount:
            key = (kend, coa)
            debit_map[key] = debit_map.get(key, 0) + amount

    coa_gaji_pengemudi = get_coa_gaji_pengemudi(company)
    for kend, amount in _compute_alokasi_gaji_opr_per_kendaraan(periode_dari, periode_sampai, company, unit).items():
        add_debit(kend, coa_gaji_pengemudi, amount)

    for r in _get_closing_bengkel_rows(periode_dari, periode_sampai, company, unit):
        if r.get("credit"):
            add_debit(r.get("kode_vra"), r.get("no_coa"), r.get("credit"))

    coa_dialokasi_kendaraan = get_coa_biaya_kendaraan_dialokasi(company)
    total_by_kendaraan = {}
    for (kend, coa), amount in debit_map.items():
        total_by_kendaraan[kend] = total_by_kendaraan.get(kend, 0) + amount

    result = []
    for (kend, coa), amount in debit_map.items():
        result.append({"no_coa": coa, "debit": amount, "credit": 0, "kode_vra": kend, "keterangan": "CLOSING VRA"})
    for kend, total in total_by_kendaraan.items():
        result.append({"no_coa": coa_dialokasi_kendaraan, "debit": 0, "credit": total, "kode_vra": kend, "keterangan": "CLOSING VRA"})

    return result


@frappe.whitelist()
def get_closing_vra_bengkel(periode_dari, periode_sampai, company=None, unit=None):
    """
    Menggabungkan semua jurnal yang masuk ke costing_bengkel_closing_vra:
      1. Alokasi Gaji Karyawan Bengkel (debit per kendaraan, credit lawan ke pool = coa_alokasi)
      2. Closing Bengkel  (debit/credit dari _get_closing_bengkel_rows)
      3. GL BKM Traksi    (alokasi gaji operator: debit 4112001, credit 4121001)
      4. Kegiatan BKM Traksi (alokasi VRA ke aktivitas)
      5. Closing VRA netting (debit Alokasi Gaji OPR + Biaya Bengkel Dialokasi, credit 4112099)
    Dipakai untuk mengisi costing_bengkel_closing_vra dan sebagai satu-satunya sumber jurnal GL.
    """
    result = []

    # --- 1. Alokasi Gaji Karyawan Bengkel ---
    coa_alokasi = get_coa_alokasi_gaji_bengkel(company)
    payslip_rows_kbn = get_payslip_karyawan_bengkel(periode_dari, periode_sampai, company, unit)
    wkt_prb_rows = get_wkt_prb_bengkel(periode_dari, periode_sampai, company)
    total_payslip_kbn = sum(r["amount"] or 0 for r in payslip_rows_kbn)
    total_wkt_prb = sum(r.total_wkt_prb or 0 for r in wkt_prb_rows)
    rate_per_jam = (total_payslip_kbn / total_wkt_prb) if total_wkt_prb else 0
    alokasi_gaji_map = {r.kendaraan: (r.total_wkt_prb or 0) * rate_per_jam for r in wkt_prb_rows}

    coa_beban_gaji = get_coa_beban_gaji_operator(company)
    for kendaraan, amount in alokasi_gaji_map.items():
        if amount:
            result.append({"no_coa": coa_alokasi, "debit": amount, "credit": 0,
                           "kode_vra": kendaraan, "keterangan": "ALOKASI GAJI KARYAWAN BENGKEL"})
            result.append({"no_coa": coa_beban_gaji, "debit": 0, "credit": amount,
                           "kode_vra": kendaraan, "keterangan": "ALOKASI GAJI KARYAWAN BENGKEL"})

    # --- 2. Closing Bengkel ---
    for r in _get_closing_bengkel_rows(periode_dari, periode_sampai, company, unit):
        result.append({"no_coa": r["no_coa"], "debit": r.get("debit", 0), "credit": r.get("credit", 0),
                       "kode_vra": r.get("kode_vra"), "keterangan": r.get("keterangan")})

    # --- 3. GL BKM Traksi ---
    for r in get_gl_bkm_traksi_bengkel(periode_dari, periode_sampai, company, unit):
        result.append({"no_coa": r["no_coa"], "debit": r.get("debit", 0), "credit": r.get("credit", 0),
                       "kode_vra": r.get("kode_vra"), "keterangan": r.get("keterangan")})

    # --- 4. Kegiatan BKM Traksi ---
    bkm_traksi_list = _get_bkm_traksi_list(periode_dari, periode_sampai, company, unit)
    for r in get_kegiatan_bkm_traksi_bengkel(bkm_traksi_list, periode_dari, periode_sampai, company, unit):
        result.append({"no_coa": r["no_coa"], "debit": r.get("debit", 0), "credit": r.get("credit", 0),
                       "kode_vra": r.get("kode_vra"), "keterangan": r.get("keterangan")})


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
    Ambil Salary Slip karyawan yang employeenya tercatat di Detail BKM Hasil Kerja Traksi
    pada Buku Kerja Mandor Traksi dalam periode tsb.
    """
    company_filter = "AND bkm.company = %(company)s" if company else ""
    unit_filter = "AND bkm.unit = %(unit)s" if unit else ""

    employees = frappe.db.sql("""
        SELECT DISTINCT hk.employee
        FROM `tabDetail BKM Hasil Kerja Traksi` hk
        JOIN `tabBuku Kerja Mandor Traksi` bkm ON bkm.name = hk.parent
        WHERE bkm.docstatus = 1
          AND bkm.posting_date BETWEEN %(dari)s AND %(sampai)s
          AND hk.employee IS NOT NULL
          AND hk.employee != ''
          {company_filter}
          {unit_filter}
    """.format(company_filter=company_filter, unit_filter=unit_filter), {
        "dari": periode_dari, "sampai": periode_sampai, "company": company, "unit": unit
    }, as_dict=True)

    if not employees:
        return []

    employee_list = tuple(e.employee for e in employees)
    ss_company_filter = "AND ss.company = %(company)s" if company else ""

    rows = frappe.db.sql("""
        SELECT
            ss.name AS salary_slip,
            ss.employee,
            ss.net_pay AS amount,
            gl.account,
            "ALOKASI GAJI OPERATOR VRA" AS keterangan
        FROM `tabSalary Slip` ss
        LEFT JOIN (
            SELECT voucher_no, account
            FROM `tabGL Entry`
            WHERE voucher_type = 'Payroll Entry'
              AND is_cancelled = 0
              AND account LIKE '4121001%%'
              AND debit > 0
            GROUP BY voucher_no, account
        ) gl ON gl.voucher_no = ss.payroll_entry
        WHERE ss.docstatus = 1
          AND ss.start_date >= %(dari)s
          AND ss.end_date <= %(sampai)s
          AND ss.employee IN %(employees)s
          {ss_company_filter}
        ORDER BY ss.start_date, ss.name
    """.format(ss_company_filter=ss_company_filter), {
        "dari": periode_dari, "sampai": periode_sampai,
        "employees": employee_list, "company": company
    }, as_dict=True)

    result = []
    for r in rows:
        result.append({
            "no_dokumen": r.salary_slip,
            "employee": r.employee,
            "no_coa": r.account,
            "amount": r.amount or 0,
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


@frappe.whitelist()
def get_coa_gaji_pengemudi(company):
    return frappe.db.get_value("Account", {"company": company, "name": ["like", "4112001%"]}, "name")


@frappe.whitelist()
def get_coa_beban_gaji_operator(company):
    return frappe.db.get_value("Account", {"company": company, "name": ["like", "4121001%"]}, "name")


def _get_kmhm_per_employee_kendaraan(periode_dari, periode_sampai, company, unit):
    """
    Selisih KM/HM per (employee, kendaraan) dari BKM Traksi.
    Jika satu BKM punya N employee di Detail BKM Hasil Kerja Traksi, selisih_kmhm dibagi N.
    """
    company_filter = "AND bkm.company = %(company)s" if company else ""
    unit_filter = "AND bkm.unit = %(unit)s" if unit else ""
    rows = frappe.db.sql("""
        SELECT
            bkm.kendaraan,
            (bkm.kmhm_akhir - bkm.kmhm_awal) AS selisih_kmhm,
            hk.employee,
            emp_count.jumlah AS jumlah_employee
        FROM `tabBuku Kerja Mandor Traksi` bkm
        JOIN `tabDetail BKM Hasil Kerja Traksi` hk ON hk.parent = bkm.name
        JOIN (
            SELECT parent, COUNT(*) AS jumlah
            FROM `tabDetail BKM Hasil Kerja Traksi`
            WHERE employee IS NOT NULL AND employee != ''
            GROUP BY parent
        ) emp_count ON emp_count.parent = bkm.name
        WHERE bkm.docstatus = 1
          AND bkm.posting_date BETWEEN %(dari)s AND %(sampai)s
          AND bkm.kendaraan IS NOT NULL AND bkm.kendaraan != ''
          AND hk.employee IS NOT NULL AND hk.employee != ''
          {company_filter}
          {unit_filter}
    """.format(company_filter=company_filter, unit_filter=unit_filter), {
        "dari": periode_dari, "sampai": periode_sampai, "company": company, "unit": unit
    }, as_dict=True)

    result = {}
    for r in rows:
        key = (r.employee, r.kendaraan)
        kmhm = (r.selisih_kmhm or 0) / (r.jumlah_employee or 1)
        result[key] = result.get(key, 0) + kmhm
    return result


def _compute_alokasi_gaji_opr_per_kendaraan(periode_dari, periode_sampai, company, unit):
    """
    Alokasi gaji operator VRA per kendaraan berdasarkan proporsi KM/HM per employee.
    Kontribusi employee ke kendaraan = (kmhm employee di kendaraan tsb / total kmhm employee) * gaji employee.
    """
    payslip_rows = get_payslip_operator_vra_bengkel(periode_dari, periode_sampai, company, unit)
    salary_per_emp = {}
    for r in payslip_rows:
        emp = r.get("employee")
        if emp:
            salary_per_emp[emp] = salary_per_emp.get(emp, 0) + (r["amount"] or 0)

    if not salary_per_emp:
        return {}

    kmhm_emp_kend = _get_kmhm_per_employee_kendaraan(periode_dari, periode_sampai, company, unit)

    total_kmhm_per_emp = {}
    for (emp, kend), kmhm in kmhm_emp_kend.items():
        total_kmhm_per_emp[emp] = total_kmhm_per_emp.get(emp, 0) + kmhm

    alokasi = {}
    for (emp, kend), kmhm in kmhm_emp_kend.items():
        total_emp_kmhm = total_kmhm_per_emp.get(emp, 0)
        salary = salary_per_emp.get(emp, 0)
        if total_emp_kmhm and salary:
            alokasi[kend] = alokasi.get(kend, 0) + (kmhm / total_emp_kmhm) * salary
    return alokasi


@frappe.whitelist()
def get_alokasi_gaji_opr_vra_bengkel(periode_dari, periode_sampai, company=None, unit=None):
    """
    Alokasi gaji operator VRA per kendaraan (whitelisted, dipakai JS).
    """
    return _compute_alokasi_gaji_opr_per_kendaraan(periode_dari, periode_sampai, company, unit)


@frappe.whitelist()
def get_kmhm_traksi_bengkel(periode_dari, periode_sampai, company=None, unit=None):
    """
    Selisih KM/HM per kendaraan dari Buku Kerja Mandor Traksi dalam periode tsb (whitelisted).
    """
    return _get_kmhm_traksi_map(periode_dari, periode_sampai, company, unit)


def _get_kmhm_traksi_map(periode_dari, periode_sampai, company, unit):
    """
    Selisih KM/HM per kendaraan dari Buku Kerja Mandor Traksi saja dalam periode tsb.
    Dipakai sebagai basis alokasi gaji operator VRA.
    """
    company_filter = "AND company = %(company)s" if company else ""
    unit_filter = "AND unit = %(unit)s" if unit else ""
    rows = frappe.db.sql("""
        SELECT kendaraan, SUM(kmhm_akhir - kmhm_awal) AS total_kmhm
        FROM `tabBuku Kerja Mandor Traksi`
        WHERE docstatus = 1
          AND posting_date BETWEEN %(dari)s AND %(sampai)s
          AND kendaraan IS NOT NULL AND kendaraan != ''
          {company_filter}
          {unit_filter}
        GROUP BY kendaraan
    """.format(company_filter=company_filter, unit_filter=unit_filter), {
        "dari": periode_dari, "sampai": periode_sampai, "company": company, "unit": unit
    }, as_dict=True)
    return {r.kendaraan: (r.total_kmhm or 0) for r in rows if r.kendaraan}


@frappe.whitelist()
def get_bkm_traksi_list_bengkel(periode_dari, periode_sampai, company=None, unit=None):
    return _get_bkm_traksi_list(periode_dari, periode_sampai, company, unit)


def _get_bkm_traksi_list(periode_dari, periode_sampai, company, unit):
    company_filter = "AND company = %(company)s" if company else ""
    unit_filter = "AND unit = %(unit)s" if unit else ""
    rows = frappe.db.sql("""
        SELECT name FROM `tabBuku Kerja Mandor Traksi`
        WHERE docstatus = 1
          AND posting_date BETWEEN %(dari)s AND %(sampai)s
          {company_filter}
          {unit_filter}
    """.format(company_filter=company_filter, unit_filter=unit_filter), {
        "dari": periode_dari, "sampai": periode_sampai, "company": company, "unit": unit
    }, as_dict=True)
    return [r.name for r in rows]


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

    coa_gaji_pengemudi = get_coa_gaji_pengemudi(company)
    for kendaraan, amount_per_kendaraan_opr in _compute_alokasi_gaji_opr_per_kendaraan(periode_dari, periode_sampai, company, unit).items():
        cb.append("costing_bengkel_alokasi_gaji_operator_vra", {
            "kode_vra": kendaraan,
            "no_coa": coa_gaji_pengemudi,
            "amount": amount_per_kendaraan_opr,
            "keterangan": "ALOKASI GAJI OPERATOR VRA",
        })

    gl_bkm_traksi_rows = get_gl_bkm_traksi_bengkel(periode_dari, periode_sampai, company, unit)
    for row in gl_bkm_traksi_rows:
        cb.append("costing_bengkel_gl_bkm_traksi", {
            "no_coa": row["no_coa"],
            "debit": row["debit"],
            "credit": row["credit"],
            "kode_vra": row["kode_vra"],
            "keterangan": row["keterangan"],
        })

    bkm_traksi_list = _get_bkm_traksi_list(periode_dari, periode_sampai, company, unit)
    kegiatan_bkm_traksi_rows = get_kegiatan_bkm_traksi_bengkel(bkm_traksi_list, periode_dari, periode_sampai, company, unit)
    for row in kegiatan_bkm_traksi_rows:
        cb.append("costing_bengkel_kegiatan_bkm_traksi", {
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
            "no_coa": row["no_coa"],
            "debit": row["debit"],
            "credit": row["credit"],
            "kode_vra": row["kode_vra"],
            "keterangan": row["keterangan"],
        })
        
    cb.insert(ignore_permissions=True)
    cb.submit()

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
