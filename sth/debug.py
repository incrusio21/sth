import frappe
from frappe import _
def debug():
	no_doc = "ACC-PAY-2026-00251"
	frappe.db.sql(""" DELETE FROM `tabPDO NON PDO Table` WHERE parent = "PDO-00070" and idx = 5 """.format())
	# frappe.db.sql(""" UPDATE `tabPurchase Invoice` SET docstatus=0 WHERE name = "{}" """.format(no_doc))
	frappe.db.sql(""" DELETE FROM `tabPayment Ledger Entry` WHERE voucher_no = "{}" """.format(no_doc))
	frappe.db.sql(""" DELETE FROM `tabGL Entry` WHERE voucher_no = "{}" """.format(no_doc))
	frappe.get_doc("Payment Entry",no_doc).on_submit()

def debug_gl():
	no_doc = "CB-2026-0003"
	# frappe.db.sql(""" DELETE FROM `tabStock Ledger Entry` WHERE voucher_no = "{}" """.format(no_doc))
	# frappe.db.sql(""" UPDATE `tabPurchase Invoice` SET docstatus=0 WHERE name = "{}" """.format(no_doc))
	frappe.db.sql(""" DELETE FROM `tabPayment Ledger Entry` WHERE voucher_no = "{}" """.format(no_doc))
	frappe.db.sql(""" DELETE FROM `tabGL Entry` WHERE voucher_no = "{}" """.format(no_doc))
	frappe.get_doc("Costing Bengkel",no_doc).on_submit()

def debug_bkm():
	lis = frappe.db.sql(""" SELECT name FROM `tabBuku Kerja Mandor Traksi` WHERE docstatus = 1 """)
	for row in lis:
		no_doc = row[0]
		frappe.db.sql(""" DELETE FROM `tabPayment Ledger Entry` WHERE voucher_no = "{}" """.format(no_doc))
		frappe.db.sql(""" DELETE FROM `tabGL Entry` WHERE voucher_no = "{}" """.format(no_doc))
		frappe.get_doc("Buku Kerja Mandor Traksi",no_doc).on_submit()
	
def debug_zero():
	# frappe.db.sql(""" UPDATE `tabPengeluaran Barang` SET docstatus=0, workflow_state="Butuh Persetujuan 1" WHERE name = "PB-020726-0002" """)
	frappe.get_doc("Payment Entry","ACC-PAY-2026-00245").submit()
	# frappe.db.sql(""" UPDATE `tabPengeluaran Barang` SET docstatus=1 WHERE name = "PB-100626-0001" """)

def debug_ap():
	no_doc="TEST - TML"
	frappe.db.sql(""" UPDATE `tabAccounting Period` SET docstatus=0, workflow_state="Draft" WHERE name = "{}" """.format(no_doc))
	frappe.get_doc("Accounting Period",no_doc).save()

def debug_list():
	li = frappe.db.sql(""" SELECT name FROM `tabDelivery Order` WHERE docstatus = 1 and grand_total > 0 """)
	for row in li:
		no_doc = row[0]
		# frappe.db.sql(""" DELETE FROM `tabStock Ledger Entry` WHERE voucher_no = "{}" """.format(no_doc))
		frappe.db.sql(""" DELETE FROM `tabPayment Ledger Entry` WHERE voucher_no = "{}" """.format(no_doc))
		frappe.db.sql(""" DELETE FROM `tabGL Entry` WHERE voucher_no = "{}" """.format(no_doc))
		frappe.get_doc("Delivery Order",no_doc).on_submit()

def rename_item(dry_run=False):
    duplicates = frappe.db.sql("""
        SELECT t1.name AS old_item, t2.name AS new_item, t1.item_name
        FROM `tabItem` t1
        JOIN `tabItem` t2
            ON t1.name != t2.name
            AND t1.item_name = t2.item_name
            AND t1.kelompok_barang = t2.kelompok_barang
            AND t1.item_group = t2.item_group
        WHERE t1.name < t2.name
        ORDER BY t1.name
    """, as_dict=True)

    if not duplicates:
        print("Tidak ada duplikat ditemukan.")
        return

    print(f"{'[DRY RUN] ' if dry_run else ''}Ditemukan {len(duplicates)} pasang duplikat:\n")

    for row in duplicates:
        old_name = row["old_item"]
        new_name = row["new_item"]
        item_name = row["item_name"]

        print(f"  {old_name} → {new_name}  ({item_name})")

        if not dry_run:
            try:
                frappe.rename_doc("Item", old_name, new_name, merge=True)
                print(f"  [OK]")
            except Exception as e:
                print(f"  [ERROR] {e}")

    if not dry_run:
        frappe.db.commit()
        print("\nSelesai. Semua perubahan di-commit.")
    else:
        print("\nDry run selesai. Tidak ada yang diubah.")