import frappe

# child table versi lama yang tidak dipakai lagi oleh Costing Mill
DOCTYPE_LAMA = (
	"Costing Mill BKM",
	"Costing Mill Stasiun",
)


def execute():
	"""Buang sisa Costing Mill versi lama dari database.

	Costing Mill dirombak: pool bengkel sekarang dibagi ke stasiun secara
	proporsional terhadap HM dan hasilnya diposting jadi GL Entry, menggantikan
	rekap tanpa jurnal yang lama. Dua child table lama ikut hilang dari kode,
	tapi menghapus file doctype tidak menghapus tabelnya — migrate membiarkan
	doctype yang sudah tidak punya berkas apa adanya.

	Dokumen Costing Mill lama ikut dibuang karena strukturnya tidak lagi cocok:
	seluruh child table-nya berganti dan tidak ada satu pun yang pernah
	memposting GL Entry, jadi tidak ada jurnal yang tertinggal menggantung.
	"""
	hapus_dokumen_costing_mill()

	for doctype in DOCTYPE_LAMA:
		if frappe.db.exists("DocType", doctype):
			frappe.delete_doc("DocType", doctype, force=True, ignore_permissions=True)


def hapus_dokumen_costing_mill():
	if not frappe.db.table_exists("Costing Mill"):
		return

	for nama in frappe.get_all("Costing Mill", pluck="name"):
		# dokumen lama tidak pernah memposting GL, tapi tetap diperiksa supaya
		# patch ini tidak diam-diam meninggalkan jurnal tanpa dokumen induk
		if frappe.db.exists("GL Entry", {"voucher_type": "Costing Mill", "voucher_no": nama}):
			frappe.log_error(
				"Costing Mill {0} punya GL Entry, tidak dihapus".format(nama),
				"hapus_costing_mill_lama"
			)
			continue

		frappe.delete_doc("Costing Mill", nama, force=True, ignore_permissions=True)
