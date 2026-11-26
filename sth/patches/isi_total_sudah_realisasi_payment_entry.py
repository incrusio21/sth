import frappe
from frappe.utils import flt

DOCTYPE = "Payment Entry"


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
	if frappe.db.has_column(DOCTYPE, "total_sudah_realisasi"):
		isi_total_sudah_realisasi()
	else:
		print("Kolom total_sudah_realisasi belum ada, langkah 1 dilewati.")

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
