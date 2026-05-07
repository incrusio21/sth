"""
DocType Controller : Transaksi Berulang
Module            : Accounting STH

Alur:
1. on_submit  → _generate_je_schedule()
   Pre-generate semua baris jadwal ke child table `je_log`.
   Akumulasi bulan-bulan yang sudah lewat digabung ke JE pertama
   yang belum tiba.

2. Scheduler (daily) → process_scheduled_je()
   Tiap hari, cek semua baris je_log dengan scheduled_date ≤ hari ini
   dan journal_entry masih kosong → buat JE otomatis.

Contoh (submit: 02 Mei 2026, tanggal_mulai: 26 Jan 2026, masa: 12):
  je_log baris 1 : scheduled_date = 26 Mei 2026, amount = premi × 5/12
                   keterangan = "Akumulasi 5 bulan (s/d Mei 2026)"
  je_log baris 2 : scheduled_date = 26 Jun 2026,  amount = premi × 1/12
  ...
  je_log baris 8 : scheduled_date = 26 Des 2026,  amount = premi × 1/12

  Pada tanggal 26 Mei 2026, scheduler membuat JE akumulasi.
  Tanggal 26 Jun–Des, scheduler membuat JE bulanan.
"""

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, add_months, today, flt


class TransaksiBerulang(Document):

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def validate(self):
        _validate(self)
        _generate_je_schedule(self)

    def on_cancel(self):
        # Batalkan JE yang sudah dibuat (yang masih Draft)
        _cancel_linked_je(self)


# ─────────────────────────────────────────────────────────────────────────────
# Generate jadwal saat submit
# ─────────────────────────────────────────────────────────────────────────────

def _generate_je_schedule(doc) -> None:
    """
    Hitung semua tanggal jadwal JE dan masukkan ke child table je_log.
    Dipanggil sekali saat on_submit.

    Akumulasi = bulan-bulan dari periode_from s/d tanggal_mulai
    JE per-bulan = bulan-bulan setelah tanggal_mulai
    """
    doc.transaksi_berulang_je_log = []

    masa         = int(doc.masa_periode)
    monthly_amt  = flt(doc.premi) / masa
    start_date   = getdate(doc.tanggal_mulai)
    periode_from = getdate(doc.periode_from)

    # ✅ Generate dari periode_from, bukan tanggal_mulai
    all_dates = [add_months(periode_from, i) for i in range(masa)]

    # ✅ Cutoff = tanggal_mulai
    # bulan s/d tanggal_mulai → akumulasi
    # bulan setelah tanggal_mulai → JE per-bulan
    past   = [d for d in all_dates if d <= start_date]
    future = sorted(d for d in all_dates if d >  start_date)

    accum_count = len(past)   # Jan, Feb, Mar, Apr, Mei = 5 ✅

    schedule = []

    if future:
        accum_amt = flt(monthly_amt * accum_count, 2)

        if accum_count > 0:
            # JE akumulasi di-post pada tanggal_mulai
            schedule.append({
                "scheduled_date": start_date,
                "amount"        : accum_amt,
                "keterangan"    : (
                    f"Akumulasi {accum_count} bulan "
                    f"({periode_from.strftime('%d %b %Y')} "
                    f"s/d {start_date.strftime('%d %b %Y')})"
                ),
            })

        # JE per-bulan untuk sisa bulan setelah tanggal_mulai
        for je_date in future:
            schedule.append({
                "scheduled_date": je_date,
                "amount"        : flt(monthly_amt, 2),
                "keterangan"    : f"Amortisasi {je_date.strftime('%B %Y')}",
            })

    else:
        # Semua tanggal sudah ≤ tanggal_mulai → satu JE akumulasi penuh
        schedule.append({
            "scheduled_date": start_date,
            "amount"        : flt(doc.premi),
            "keterangan"    : (
                f"Akumulasi semua {masa} bulan "
                f"({periode_from.strftime('%d %b %Y')} "
                f"s/d {start_date.strftime('%d %b %Y')})"
            ),
        })

    for row in schedule:
        doc.append("transaksi_berulang_je_log", {
            "doctype"        : "Transaksi Berulang JE Log",
            "parent"         : doc.name,
            "parenttype"     : "Transaksi Berulang",
            "parentfield"    : "transaksi_berulang_je_log",
            "scheduled_date" : row["scheduled_date"],
            "amount"         : row["amount"],
            "keterangan"     : row["keterangan"],
            "journal_entry"  : None,
        })
# ─────────────────────────────────────────────────────────────────────────────
# Scheduled task – dipanggil Frappe setiap hari
# ─────────────────────────────────────────────────────────────────────────────

def process_scheduled_je() -> None:
    """
    Entry point untuk scheduler Frappe (daily).
    Daftarkan di hooks.py → scheduler_events → daily.
    """
    today_date = getdate(today())
    company    = _get_company()

    # Cari semua baris je_log yang sudah due dan belum dibuatkan JE
    due_rows = frappe.db.sql("""
        SELECT
            name,
            parent,
            scheduled_date,
            amount,
            keterangan
        FROM `tabTransaksi Berulang JE Log`
        WHERE scheduled_date <= %s
            AND (journal_entry IS NULL OR journal_entry = '')
            AND docstatus = 1
        ORDER BY scheduled_date ASC
    """, (today_date,), as_dict=True)

    if not due_rows:
        return

    # Group per parent agar get_doc hanya sekali per dokumen
    parent_map: dict[str, list] = {}
    for row in due_rows:
        parent_map.setdefault(row.parent, []).append(row)

    for docname, rows in parent_map.items():
        try:
            doc = frappe.get_doc("Transaksi Berulang", docname)
            _process_due_rows(doc, rows, company)
            frappe.db.commit()
        except Exception:
            frappe.db.rollback()
            frappe.log_error(
                frappe.get_traceback(),
                f"Transaksi Berulang – gagal buat JE untuk {docname}",
            )


def _process_due_rows(doc, rows: list, company: str) -> None:
    """Buat JE untuk setiap baris yang sudah jatuh tempo."""
    for row_data in rows:
        je_name = _make_je(
            doc       = doc,
            company   = company,
            post_date = getdate(row_data.scheduled_date),
            amount    = flt(row_data.amount),
            remark    = f"{row_data.keterangan} — {doc.name}",
        )

        frappe.db.set_value(
            "Transaksi Berulang JE Log",
            row_data.name,
            "journal_entry",
            je_name,
        )

        frappe.logger().info(
            f"[Transaksi Berulang] JE {je_name} dibuat "
            f"({row_data.keterangan}) untuk {doc.name} "
            f"tanggal {row_data.scheduled_date}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Buat satu Journal Entry
# ─────────────────────────────────────────────────────────────────────────────

def _make_je(doc, company: str, post_date, amount: float, remark: str) -> str:
    je = frappe.new_doc("Journal Entry")
    je.voucher_type = "Journal Entry"
    je.posting_date = post_date
    je.company      = company
    je.user_remark  = remark
    je.transaksi_berulang = doc.name

    cost_center = frappe.db.get_value("Company", company, "cost_center")

    je.append("accounts", {
        "account"                   : doc.jurnal_debit,
        "debit_in_account_currency" : amount,
        "credit_in_account_currency": 0,
        "cost_center"               : cost_center,
    })
    je.append("accounts", {
        "account"                   : doc.jurnal_kredit,
        "debit_in_account_currency" : 0,
        "credit_in_account_currency": amount,
        "cost_center"               : cost_center,
    })
    
    je.insert(ignore_permissions=True)
    je.submit()
    frappe.db.commit()
    return je.name


# ─────────────────────────────────────────────────────────────────────────────
# Cancel: batalkan JE draft yang terkait
# ─────────────────────────────────────────────────────────────────────────────

def _cancel_linked_je(doc) -> None:
    linked = frappe.get_list(
        "Transaksi Berulang JE Log",
        filters={"parent": doc.name, "journal_entry": ["is", "set"]},
        fields=["journal_entry"],
    )
    for row in linked:
        je_doc = frappe.get_doc("Journal Entry", row.journal_entry)
        if je_doc.docstatus == 1:
            je_doc.cancel()
        elif je_doc.docstatus == 0:
            je_doc.delete()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _validate(doc) -> None:
    required = {
        "tanggal_mulai": "Tanggal Mulai",
        "masa_periode" : "Masa Periode",
        "premi"        : "Premi",
        "jurnal_debit" : "Jurnal Debit (COA)",
        "jurnal_kredit": "Jurnal Kredit (COA)",
    }
    missing = [label for field, label in required.items() if not doc.get(field)]
    if missing:
        frappe.throw(
            f"Field wajib belum diisi: <b>{', '.join(missing)}</b>",
            title="Validasi Gagal",
        )
    if int(doc.masa_periode or 0) <= 0:
        frappe.throw("Masa Periode harus lebih dari 0.", title="Validasi Gagal")
    if flt(doc.premi) <= 0:
        frappe.throw("Premi harus lebih dari 0.", title="Validasi Gagal")


def _get_company() -> str:
    company = (
        frappe.defaults.get_user_default("Company")
        or frappe.db.get_single_value("Global Defaults", "default_company")
    )
    if not company:
        frappe.throw(
            "Default Company belum disetel. Cek Global Defaults atau User Defaults.",
            title="Company Tidak Ditemukan",
        )
    return company
