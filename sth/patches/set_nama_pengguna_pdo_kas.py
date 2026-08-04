import frappe


def execute():
	"""Kolom nama_pengguna baru ditambahkan di PDO Kas Table. Isi baris lama
	dari master Employee berdasarkan kode yang tersimpan di kolom employee."""
	frappe.db.sql(
		"""
		UPDATE `tabPDO Kas Table` kas
		INNER JOIN `tabEmployee` emp ON emp.name = kas.employee
		SET kas.nama_pengguna = emp.employee_name
		WHERE IFNULL(kas.employee, '') != ''
			AND IFNULL(kas.nama_pengguna, '') = ''
		"""
	)

	# kode yang tidak ada di master Employee tidak bisa diterjemahkan,
	# biarkan kosong tapi laporkan jumlahnya
	sisa = frappe.db.sql(
		"""
		SELECT COUNT(*)
		FROM `tabPDO Kas Table`
		WHERE IFNULL(employee, '') != ''
			AND IFNULL(nama_pengguna, '') = ''
		"""
	)[0][0]

	if sisa:
		print(f"PDO Kas Table: {sisa} baris pengguna tidak ketemu di master Employee")
