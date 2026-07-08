# copy_item.py
# bench --site site-b.example.com execute copy_item.main --args '["ITEM-001"]'
# bench --site site-b.example.com execute copy_item.main --args '[["ITEM-001","ITEM-002"]]'

import requests
import frappe

# ── Konfigurasi Site A ────────────────────────────────────
SITE_A = "https://dev-erp.sthgroup.com"
API_KEY_A = "54fe04a950b4506"
API_SECRET_A = "5a70a5e885ff6a4"
# ─────────────────────────────────────────────────────────

ITEM_DEPENDENCIES = [
    ("Item Group",              "item_group"),
    ("UOM",                     "stock_uom"),
    ("UOM",                     "purchase_uom"),
    ("UOM",                     "sales_uom"),
    ("Brand",                   "brand"),
    ("Item Tax Template",       "taxes"),
    ("Currency",                "valuation_currency"),
]

REMOVE_FIELDS = {"name", "creation", "modified", "modified_by", "owner", "docstatus"}
REMOVE_CHILD_FIELDS = REMOVE_FIELDS | {"parent", "parenttype", "parentfield", "idx"}

COPYABLE_DOCTYPES = {"UOM", "Brand", "Item Tax Template", "Item Group"}


def get_headers():
    return {
        "Authorization": f"token {API_KEY_A}:{API_SECRET_A}",
        "Content-Type": "application/json",
    }


def fetch_from_a(doctype, name):
    url = f"{SITE_A}/api/resource/{requests.utils.quote(doctype)}/{requests.utils.quote(name)}"
    r = requests.get(url, headers=get_headers())
    r.raise_for_status()
    return r.json()["data"]


def clean_doc(doc):
    cleaned = {k: v for k, v in doc.items() if k not in REMOVE_FIELDS}
    for key, value in cleaned.items():
        if isinstance(value, list):
            cleaned[key] = [
                {k: v for k, v in row.items() if k not in REMOVE_CHILD_FIELDS}
                for row in value
            ]
    return cleaned


def insert_to_b(doctype, data):
    workflow_state = data.pop("workflow_state", None)

    for key, value in data.items():
        if isinstance(value, list) and value:
            field_meta = frappe.get_meta(doctype).get_field(key)
            if field_meta and field_meta.options:
                data[key] = ensure_child_links(field_meta.options, value)

    doc = frappe.get_doc({"doctype": doctype, **data})
    doc.flags.ignore_permissions = True
    doc.flags.ignore_validate = True
    doc.insert()

    if workflow_state:
        frappe.db.set_value(doctype, doc.name, "workflow_state", workflow_state, update_modified=False)

    frappe.db.commit()
    return doc.name


def ensure_linked_doc(doctype, name):
    if not name or frappe.db.exists(doctype, name):
        return

    if doctype not in COPYABLE_DOCTYPES:
        print(f"    ⚠️  '{doctype}' '{name}' tidak ada di Site B dan tidak di-copy otomatis")
        return

    try:
        print(f"    Fetching {doctype} '{name}' dari Site A...")
        doc = fetch_from_a(doctype, name)

        if doctype == "Item Group":
            parent = doc.get("parent_item_group")
            if parent:
                ensure_linked_doc("Item Group", parent)

        cleaned = clean_doc(doc)
        insert_to_b(doctype, cleaned)
        print(f"    ✅ {doctype} '{name}' dibuat di Site B")

    except Exception as e:
        print(f"    ❌ Gagal copy {doctype} '{name}': {e}")


def ensure_child_links(doctype, rows):
    if not rows:
        return rows

    link_fields = frappe.get_all(
        "DocField",
        filters={"parent": doctype, "fieldtype": "Link"},
        fields=["fieldname", "options"],
    )

    valid_rows = []
    for row in rows:
        broken = False
        for lf in link_fields:
            value = row.get(lf["fieldname"])
            if not value:
                continue
            if not frappe.db.exists(lf["options"], value):
                ensure_linked_doc(lf["options"], value)
                if not frappe.db.exists(lf["options"], value):
                    print(f"    ⚠️  Skip row di '{doctype}': {lf['fieldname']} = '{value}' tidak ditemukan")
                    broken = True
                    break
        if not broken:
            valid_rows.append(row)

    return valid_rows


def ensure_item_group(name):
    if not name or frappe.db.exists("Item Group", name):
        if name:
            print(f"    [skip] Item Group '{name}' sudah ada")
        return

    doc = fetch_from_a("Item Group", name)
    parent = doc.get("parent_item_group")
    if parent:
        ensure_item_group(parent)

    insert_to_b("Item Group", clean_doc(doc))
    print(f"    ✅ Item Group '{name}' dibuat")


def ensure_dependency(doctype, name):
    if not name or frappe.db.exists(doctype, name):
        if name:
            print(f"    [skip] {doctype} '{name}' sudah ada")
        return

    doc = fetch_from_a(doctype, name)
    insert_to_b(doctype, clean_doc(doc))
    print(f"    ✅ {doctype} '{name}' dibuat")


def delete_item_if_exists(item_code, item_name_field=None):
    names_to_delete = set()

    if frappe.db.exists("Item", item_code):
        names_to_delete.add(item_code)

    if item_name_field:
        dupes = frappe.get_all(
            "Item",
            filters={"item_name": item_name_field},
            pluck="name",
        )
        names_to_delete.update(dupes)

    if not names_to_delete:
        return

    child_doctypes = frappe.get_all(
        "DocField",
        filters={"fieldtype": "Table", "parent": "Item"},
        pluck="options",
    )

    for name in names_to_delete:
        print(f"  Menghapus item lama '{name}' di Site B...")
        for child_doctype in child_doctypes:
            rows = frappe.get_all(child_doctype, filters={"parent": name}, pluck="name")
            for row_name in rows:
                frappe.delete_doc(child_doctype, row_name, ignore_permissions=True, force=True)
            if rows:
                print(f"    Hapus {len(rows)} rows dari '{child_doctype}'")

        frappe.delete_doc("Item", name, ignore_permissions=True, force=True)
        frappe.db.commit()
        print(f"  ✅ Item '{name}' selesai dihapus")


def copy_item(item_code):
    print(f"\n{'='*50}")
    print(f"Item: {item_code}")

    item = fetch_from_a("Item", item_code)

    for key, val in item.items():
        if isinstance(val, list) and val:
            print(f"  Child table '{key}': {len(val)} rows")

    print("  Memeriksa dependencies...")
    for doctype, field in ITEM_DEPENDENCIES:
        value = item.get(field)
        if not value:
            continue
        if doctype == "Item Group":
            ensure_item_group(value)
        else:
            ensure_dependency(doctype, value)

    delete_item_if_exists(item_code, item.get("item_name"))

    name = insert_to_b("Item", clean_doc(item))
    print(f"✅ Item '{name}' berhasil dibuat")


def main(item_codes=None):
    if isinstance(item_codes, str):
        item_codes = [item_codes]
    if not item_codes:
        print("Usage: bench execute copy_item.main --args '[\"ITEM-001\"]'")
        return

    errors = []
    for code in item_codes:
        try:
            copy_item(code)
        except Exception as e:
            msg = f"❌ Gagal '{code}': {e}"
            print(msg)
            errors.append(msg)

    print(f"\n{'='*50}")
    print(f"Selesai. {len(item_codes) - len(errors)} berhasil, {len(errors)} gagal.")
    for e in errors:
        print(f"  {e}")

def bersih():
    list_item = frappe.db.sql(""" 
        SELECT name, item_name 
        FROM `tabItem` 
        WHERE date(creation) < date(now()) 
        AND (kode_kelompok_barang != "313" OR kode_kelompok_barang IS NULL )""")
    for row in list_item:
        delete_item_if_exists(row[0])

def main_all(batch_size=50):
    print("Fetching daftar semua item dari Site A...")

    headers = get_headers()
    all_codes = []
    start = 0

    while True:
        url = f"{SITE_A}/api/resource/Item?fields=[\"name\"]&limit={batch_size}&limit_start={start}"
        r = requests.get(url, headers=headers)
        r.raise_for_status()
        data = r.json().get("data", [])
        if not data:
            break
        all_codes.extend([d["name"] for d in data])
        start += batch_size
        if len(data) < batch_size:
            break

    print(f"Total item ditemukan: {len(all_codes)}")

    errors = []
    for i, code in enumerate(all_codes, 1):
        print(f"\n[{i}/{len(all_codes)}]")
        try:
            copy_item(code)
        except Exception as e:
            msg = f"❌ Gagal '{code}': {e}"
            print(msg)
            errors.append(msg)

    print(f"\n{'='*50}")
    print(f"Selesai. {len(all_codes) - len(errors)} berhasil, {len(errors)} gagal.")
    for e in errors:
        print(f"  {e}")