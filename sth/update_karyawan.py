"""
Update data Employee di ERPNext langsung lewat Frappe API (bench console / bench execute),
tanpa perlu API key/secret atau site URL.

Mapping kolom CSV -> field Employee:
    ID              -> dipakai sebagai docname (name) Employee
    NIP             -> custom_nip
    Kode Kemandoran -> kemandoran
    Kode Divisi     -> divisi

CARA PAKAI (paling gampang, lewat bench console):
    $ bench --site [nama_site] console
    >>> exec(open('/path/ke/update_karyawan_bench.py').read())
    >>> execute('/path/ke/Update_Karyawan.csv', dry_run=1)   # cek dulu, tidak nulis apa-apa
    >>> execute('/path/ke/Update_Karyawan.csv')              # jalankan beneran (commit)

ALTERNATIF (lewat bench execute, kalau file ini sudah kamu taruh sebagai module
di dalam salah satu app, mis. apps/erpnext/erpnext/update_karyawan_bench.py):
    $ bench --site [nama_site] execute erpnext.update_karyawan_bench.execute \\
        --kwargs "{'csv_path': '/path/ke/Update_Karyawan.csv', 'dry_run': 1}"
"""

import csv

import frappe

DOCTYPE = "Employee"

# kolom CSV -> field Employee
FIELD_MAP = {
    "NIP": "custom_nip",
    "Kode Kemandoran": "kemandoran",
    "Kode Divisi": "divisi",
}
ID_COLUMN = "ID"


def execute(dry_run=0):
    csv_path = "/home/frappe/frappe-bench/apps/sth/sth/Update_Karyawan.csv"
    """
    csv_path: path ke Update_Karyawan.csv di server
    dry_run : 1 = cuma print rencana update, tidak menyentuh database
              0 = update beneran + commit (default)
    """
    dry_run = int(dry_run)

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    missing_cols = ({ID_COLUMN, *FIELD_MAP} - set(reader.fieldnames or []))
    if missing_cols:
        frappe.throw(f"Kolom CSV tidak lengkap, hilang: {missing_cols}")

    print(f"Total baris: {len(rows)} | mode: {'DRY-RUN' if dry_run else 'UPDATE'}")

    ok, skipped, failed = 0, 0, 0
    log_rows = []

    for i, row in enumerate(rows, start=1):
        employee_id = (row.get(ID_COLUMN) or "").strip()

        if not employee_id:
            skipped += 1
            log_rows.append((employee_id, "SKIP", "ID kosong"))
            continue

        if not frappe.db.exists(DOCTYPE, employee_id):
            skipped += 1
            log_rows.append((employee_id, "SKIP", "Employee tidak ditemukan"))
            print(f"[{i}/{len(rows)}] {employee_id}: SKIP (tidak ditemukan)")
            continue

        # cuma masukkan field yang isinya tidak kosong di CSV
        values = {
            field: (row.get(csv_col) or "").strip()
            for csv_col, field in FIELD_MAP.items()
            if (row.get(csv_col) or "").strip()
        }

        if dry_run:
            print(f"[{i}/{len(rows)}] (dry-run) {employee_id} -> {values}")
            ok += 1
            continue

        try:
            doc = frappe.get_doc(DOCTYPE, employee_id)
            for field, value in values.items():
                doc.set(field, value)
            doc.save()  # lewat validate() dan hooks lain, bukan tulis langsung ke DB
            ok += 1
            log_rows.append((employee_id, "OK", ""))
            print(f"[{i}/{len(rows)}] {employee_id}: OK")
        except Exception as e:
            failed += 1
            frappe.db.rollback()  # batalkan perubahan sebagian pada doc ini kalau gagal
            log_rows.append((employee_id, "GAGAL", str(e)))
            print(f"[{i}/{len(rows)}] {employee_id}: GAGAL - {e}")

    if not dry_run:
        frappe.db.commit()

    print(f"\nSelesai. OK: {ok}, Skip: {skipped}, Gagal: {failed}")

    log_path = "update_karyawan_result.csv"
    with open(log_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "status", "detail"])
        writer.writerows(log_rows)
    print(f"Log tersimpan di: {log_path}")

    return {"ok": ok, "skipped": skipped, "failed": failed}