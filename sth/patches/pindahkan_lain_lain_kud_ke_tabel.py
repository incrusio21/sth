import frappe
from frappe.utils import cint, flt


def execute():
	"""Pindahkan Lain Lain Perhitungan KUD dari satu angka + satu akun ke tabel Rincian Lain Lain.

	Satu dokumen lama memuat tepat satu Lain Lain, jadi tiap dokumen yang Lain
	Lain-nya tidak nol menghasilkan satu baris berakun `akun_lain_lain` lamanya.
	Dokumen yang sudah punya baris dilewati, jadi patch ini aman diulang.

	Dokumen yang sudah disubmit ikut dipindah, supaya Lain Lain-nya tidak hilang
	kalau dokumen itu dibatalkan lalu di-amend. Barisnya disisipkan lewat
	db_insert, bukan save(), supaya tidak ada validate maupun on_submit yang jalan
	ulang di dokumen yang jurnalnya sudah ada. Kolom `akun_lain_lain` dibiarkan:
	fieldnya sudah dibuang dari doctype, dan isinya tetap jadi jejak.
	"""
	kolom_akun = (
		"akun_lain_lain" if frappe.db.has_column("Perhitungan KUD", "akun_lain_lain") else "NULL"
	)

	dokumen = frappe.db.sql(
		f"""
		SELECT p.name, p.docstatus, p.owner, p.modified_by, p.creation, p.modified,
		       p.lain_lain, {kolom_akun} AS akun_lain_lain
		FROM `tabPerhitungan KUD` p
		WHERE IFNULL(p.lain_lain, 0) != 0
		  AND NOT EXISTS (
		      SELECT 1 FROM `tabPerhitungan KUD Lain Lain` c
		      WHERE c.parent = p.name AND c.parenttype = 'Perhitungan KUD'
		  )
		ORDER BY p.creation
		""",
		as_dict=True,
	)

	for doc in dokumen:
		baris = frappe.new_doc("Perhitungan KUD Lain Lain")
		baris.update({
			"akun": doc.akun_lain_lain,
			"jumlah": flt(doc.lain_lain),
		})

		baris.parent = doc.name
		baris.parenttype = "Perhitungan KUD"
		baris.parentfield = "rincian_lain_lain"
		baris.idx = 1
		baris.docstatus = cint(doc.docstatus)
		baris.owner = doc.owner
		baris.modified_by = doc.modified_by
		baris.creation = doc.creation
		baris.modified = doc.modified

		baris.db_insert()

	frappe.db.commit()
	print("Lain Lain Perhitungan KUD dipindah ke tabel: {}".format(len(dokumen)))
