import frappe

DOCTYPES = ("Leave Application", "Expense Claim", "Travel Request")
FIELDNAME = "department_name"


def execute():
	"""Isi Department Name di Leave Application, Expense Claim, dan Travel Request lama.

	Field department_name baru ditambahkan (fetch_from department.department_name)
	supaya nama tampilan Department terbaca tanpa akhiran singkatan company.
	fetch_from hanya jalan waktu department dipilih atau dokumen disimpan, jadi
	dokumen lama - termasuk yang sudah submit - masih kosong.

	Sumbernya Department yang tercatat di dokumen itu sendiri, bukan department
	Employee saat ini, supaya karyawan yang sudah pindah tidak ikut mengubah
	dokumen lamanya. Dokumen yang department_name-nya sudah terisi dilewati, jadi
	aman dijalankan berulang kali.
	"""
	for doctype in DOCTYPES:
		pastikan_custom_field(doctype)

		kondisi = """
			FROM `tab{0}` d
			INNER JOIN `tabDepartment` dep ON dep.name = d.department
			WHERE COALESCE(d.`{1}`, '') = ''
				AND COALESCE(dep.department_name, '') != ''
		""".format(doctype, FIELDNAME)

		perlu_diisi = frappe.db.sql("SELECT COUNT(*) {0}".format(kondisi))[0][0]
		if not perlu_diisi:
			print("Semua {0} sudah punya Department Name, dilewati.".format(doctype))
			continue

		# Ditulis ulang, bukan dipakai ulang dari `kondisi`: di sintaks UPDATE, SET
		# duduk di antara JOIN dan WHERE.
		frappe.db.sql(
			"""
			UPDATE `tab{0}` d
			INNER JOIN `tabDepartment` dep ON dep.name = d.department
			SET d.`{1}` = dep.department_name
			WHERE COALESCE(d.`{1}`, '') = ''
				AND COALESCE(dep.department_name, '') != ''
			""".format(doctype, FIELDNAME)
		)

		print("{0} {1} diisi Department Name-nya.".format(perlu_diisi, doctype))


def pastikan_custom_field(doctype):
	"""Pastikan kolom department_name sudah ada sebelum diisi.

	Patch post_model_sync jalan sebelum sync_customizations() milik migrate, jadi
	di site yang custom field-nya belum pernah tersinkron, kolomnya belum ada
	waktu patch ini kena giliran. Disinkronkan duluan di sini; migrate tetap
	menyinkronkan lagi setelahnya dan itu tidak masalah karena sync_customizations
	idempoten.
	"""
	from frappe.modules.utils import sync_customizations

	if frappe.get_meta(doctype).get_field(FIELDNAME):
		return

	sync_customizations(app="sth")
	frappe.clear_cache(doctype=doctype)

	# cached=False supaya tidak kena meta yang masih tersimpan di proses ini.
	if not frappe.get_meta(doctype, cached=False).get_field(FIELDNAME):
		frappe.throw("Custom field {0} gagal disinkronkan ke {1}.".format(FIELDNAME, doctype))
