import json
import os

import frappe

from sth.patches.isi_total_sudah_realisasi_payment_entry import kolom_ada

DOCTYPE = "Payment Entry"


def pastikan_field_total_plafon_pdo_ada():
	"""Pasang Custom Field total_plafon_pdo sebelum diisi.

	Alasannya sama dengan isi_total_sudah_realisasi_payment_entry: folder custom/
	baru disinkronkan sesudah semua patch, dan di produksi sinkronisasinya pernah
	tidak sampai ke ALTER TABLE.
	"""
	from frappe.modules.utils import sync_customizations_for_doctype

	folder = frappe.get_app_path("sth", "finance_sth", "custom")
	with open(os.path.join(folder, "payment_entry.json")) as f:
		sync_customizations_for_doctype(json.load(f), folder)

	frappe.db.commit()

	if not kolom_ada("total_plafon_pdo"):
		frappe.db.sql_ddl(
			"alter table `tabPayment Entry` add column if not exists "
			"`total_plafon_pdo` decimal(21,9) not null default 0"
		)
		print("Kolom total_plafon_pdo ditambahkan langsung ke tabPayment Entry.")

	cache = frappe.cache() if callable(frappe.cache) else frappe.cache
	cache.hdel("table_columns", "tabPayment Entry")


def execute():
	"""Isi Total Plafon PDO untuk semua Realisasi PDO yang belum batal.

	Plafon diambil dari PDO apa adanya sekarang (nilai revisi yang menang), sama
	dengan hitungan di form.
	"""
	from sth.custom.payment_entry import hitung_total_plafon_pdo

	pastikan_field_total_plafon_pdo_ada()

	pe_list = frappe.get_all(
		DOCTYPE,
		filters={"tipe_transfer": "Realisasi PDO", "docstatus": ["<", 2]},
		pluck="name",
	)

	diubah = 0
	gagal = []
	for name in pe_list:
		rows = frappe.get_all(
			"Payment Voucher Kas PDO",
			filters={"parent": name, "parenttype": DOCTYPE},
			fields=["no_pdo", "tipe_pdo", "item_barang"],
		)
		try:
			total = hitung_total_plafon_pdo(rows)
		except frappe.DoesNotExistError:
			# PDO-nya sudah dihapus; plafonnya tidak bisa dihitung lagi.
			frappe.clear_last_message()
			gagal.append(name)
			continue

		frappe.db.set_value(DOCTYPE, name, "total_plafon_pdo", total, update_modified=False)
		diubah += 1

	print("Total Plafon PDO diisi pada {0} Payment Entry Realisasi PDO.".format(diubah))
	if gagal:
		print("Dilewati karena PDO-nya tidak ada: {0}".format(", ".join(gagal)))
