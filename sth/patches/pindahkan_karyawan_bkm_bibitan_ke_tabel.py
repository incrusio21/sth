import frappe


def execute():
	"""Pindahkan karyawan BKM Bibitan dari header ke tabel hasil kerja.

	Satu BKM Bibitan lama memuat tepat satu karyawan di field employee dan qty.
	Field itu sudah dihapus dari doctype, tapi kolomnya masih ada di tabel
	database, jadi isinya dibaca dari sana dan dijadikan satu baris Detail BKM
	Hasil Kerja Bibitan. Dokumen yang sudah punya baris dilewati, jadi patch ini
	aman diulang.

	Dokumen yang sudah disubmit ikut dipindah. Barisnya disisipkan lewat
	db_insert, bukan save(), supaya tidak ada validate maupun on_submit yang
	jalan ulang — BKM Perawatan salinannya sudah memuat karyawan yang sama.
	"""
	if not frappe.db.has_column("Buku Kerja Mandor Bibitan", "employee"):
		return

	dokumen = frappe.db.sql("""
		SELECT bbt.name, bbt.docstatus, bbt.employee, bbt.qty,
			bbt.owner, bbt.modified_by, bbt.creation, bbt.modified
		FROM `tabBuku Kerja Mandor Bibitan` bbt
		WHERE IFNULL(bbt.employee, '') != ''
			AND NOT EXISTS (
				SELECT 1 FROM `tabDetail BKM Hasil Kerja Bibitan` hk
				WHERE hk.parent = bbt.name AND hk.parenttype = 'Buku Kerja Mandor Bibitan'
			)
		ORDER BY bbt.creation
	""", as_dict=True)

	for doc in dokumen:
		karyawan = frappe.db.get_value(
			"Employee", doc.employee, ["employee_name", "no_ktp"], as_dict=True
		) or {}

		baris = frappe.new_doc("Detail BKM Hasil Kerja Bibitan")
		baris.update({
			"parent": doc.name,
			"parenttype": "Buku Kerja Mandor Bibitan",
			"parentfield": "hasil_kerja",
			"idx": 1,
			"docstatus": doc.docstatus,
			"employee": doc.employee,
			"employee_name": karyawan.get("employee_name"),
			"no_ktp": karyawan.get("no_ktp"),
			"qty": doc.qty,
			"owner": doc.owner,
			"modified_by": doc.modified_by,
			"creation": doc.creation,
			"modified": doc.modified,
		})
		baris.db_insert()

	frappe.db.commit()
	print("BKM Bibitan dipindah ke tabel hasil kerja: {}".format(len(dokumen)))
