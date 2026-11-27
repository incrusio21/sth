import json
import os

import frappe
from frappe.utils import flt

DOCTYPE = "Payment Entry"


def pastikan_field_total_sudah_realisasi_ada():
	"""Pasang Custom Field total_sudah_realisasi lebih dulu.

	bench migrate menyinkronkan folder custom/ sesudah semua patch, sedangkan
	field ini lahir bareng patch-nya. Tanpa ini langkah 1 selalu dilewati di
	migrate pertama dan patch tercatat selesai. Tidak dijaga has_column():
	daftar kolom dibaca dari cache.
	"""
	from frappe.modules.utils import sync_customizations_for_doctype

	folder = frappe.get_app_path("sth", "finance_sth", "custom")
	with open(os.path.join(folder, "payment_entry.json")) as f:
		sync_customizations_for_doctype(json.load(f), folder)

	frappe.db.commit()

	# Di bench migrate produksi sinkronisasi di atas tidak selalu sampai ke
	# ALTER TABLE (26 Nov 2026: "Unknown column total_sudah_realisasi"), padahal
	# lewat run-patch berhasil. Kolomnya dipastikan langsung dari
	# information_schema, bukan dari cache daftar kolom.
	if not kolom_ada("total_sudah_realisasi"):
		frappe.db.sql_ddl(
			"alter table `tabPayment Entry` add column if not exists "
			"`total_sudah_realisasi` decimal(21,9) not null default 0"
		)
		print("Kolom total_sudah_realisasi ditambahkan langsung ke tabPayment Entry.")

	cache = frappe.cache() if callable(frappe.cache) else frappe.cache
	cache.hdel("table_columns", "tabPayment Entry")


def kolom_ada(fieldname):
	return bool(frappe.db.sql(
		"""
		select 1 from information_schema.columns
		where table_schema = database()
			and table_name = 'tabPayment Entry'
			and column_name = %s
		""",
		fieldname,
	))


def execute():
	"""Isi data lama untuk Realisasi PDO setelah field Total Sudah Direalisasi
	dan aturan sisa List Kas ditambahkan.

	1. Total Sudah Direalisasi untuk semua Realisasi PDO yang belum batal.
	   - Draft: semua PV lain yang sudah tersubmit, sama dengan hitungan di form.
	   - Tersubmit: hanya PV tersubmit yang dibuat lebih dulu, supaya angkanya
	     menggambarkan keadaan saat PV itu dibuat dan tidak ikut membengkak
	     oleh PV yang datang belakangan. Urutannya memakai `creation`, karena
	     Payment Entry tidak menyimpan waktu submit.
	2. Realisasi Tambahan dicentang pada PV yang belum tersubmit kalau baris
	   Kas-nya melewati sisa List Kas, supaya approval-nya pindah ke jalur
	   tambahan. PV tersubmit dibiarkan.
	"""
	pastikan_field_total_sudah_realisasi_ada()
	isi_total_sudah_realisasi()

	if frappe.db.has_column(DOCTYPE, "realisasi_tambahan"):
		tandai_draft_melebihi_sisa_kas()
	else:
		print("Kolom realisasi_tambahan belum ada, langkah 2 dilewati.")


def isi_total_sudah_realisasi():
	pe_list = frappe.db.sql("""
		select name, docstatus, creation
		from `tabPayment Entry`
		where tipe_transfer = 'Realisasi PDO'
			and docstatus < 2
	""", as_dict=True)

	if not pe_list:
		return

	baris = frappe.db.sql("""
		select baris.name, baris.parent, baris.no_pdo, baris.tipe_pdo,
			baris.item_barang, baris.total
		from `tabPayment Voucher Kas PDO` baris
		inner join `tabPayment Entry` pe on pe.name = baris.parent
		where baris.parenttype = 'Payment Entry'
			and pe.tipe_transfer = 'Realisasi PDO'
			and pe.docstatus < 2
	""", as_dict=True)

	info_pe = {pe.name: pe for pe in pe_list}
	baris_per_pe = {}
	for row in baris:
		baris_per_pe.setdefault(row.parent, []).append(row)

	# Baris dari PV tersubmit, dikelompokkan per (no_pdo, tipe_pdo) supaya
	# pencocokan per PV tidak perlu memindai semua baris.
	submit_per_kunci = {}
	for row in baris:
		if info_pe[row.parent].docstatus != 1 or not (row.no_pdo and row.tipe_pdo):
			continue
		submit_per_kunci.setdefault((row.no_pdo, row.tipe_pdo), []).append(row)

	diubah = 0
	for pe in pe_list:
		kunci = set()
		for row in baris_per_pe.get(pe.name, []):
			if row.no_pdo and row.tipe_pdo:
				kunci.add((row.no_pdo, row.tipe_pdo, row.item_barang or None))

		terhitung = {}
		for no_pdo, tipe_pdo, item_barang in kunci:
			for lain in submit_per_kunci.get((no_pdo, tipe_pdo), []):
				if lain.parent == pe.name:
					continue
				if item_barang and lain.item_barang != item_barang:
					continue
				if pe.docstatus == 1 and info_pe[lain.parent].creation >= pe.creation:
					continue
				terhitung[lain.name] = flt(lain.total)

		total = flt(sum(terhitung.values()))
		frappe.db.set_value(DOCTYPE, pe.name, "total_sudah_realisasi", total, update_modified=False)
		diubah += 1

	print("Total Sudah Direalisasi diisi pada {0} Payment Entry Realisasi PDO.".format(diubah))


def tandai_draft_melebihi_sisa_kas():
	from sth.custom.payment_entry import baris_kas_melebihi_sisa

	daftar = frappe.db.sql_list("""
		select distinct pe.name
		from `tabPayment Entry` pe
		inner join `tabPayment Voucher Kas PDO` baris
			on baris.parent = pe.name
			and baris.parenttype = 'Payment Entry'
		where pe.docstatus = 0
			and pe.tipe_transfer = 'Realisasi PDO'
			and coalesce(pe.realisasi_tambahan, 0) = 0
			and baris.tipe_pdo = 'Kas'
			and coalesce(baris.pdo_child_name, '') != ''
	""")

	ditandai = []
	for name in daftar:
		doc = frappe.get_doc(DOCTYPE, name)
		if baris_kas_melebihi_sisa(doc):
			frappe.db.set_value(DOCTYPE, name, "realisasi_tambahan", 1, update_modified=False)
			ditandai.append(name)

	if ditandai:
		print("Realisasi Tambahan dicentang pada {0} PV draft yang melewati sisa List Kas: {1}".format(
			len(ditandai), ", ".join(ditandai)
		))
	else:
		print("Tidak ada PV draft yang melewati sisa List Kas.")
