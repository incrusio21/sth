import frappe


def execute():
	"""trans_no jadi unique. Baris lama menyimpan '' (bukan NULL) dan '' ganda
	membuat pembuatan unique index gagal, jadi kosongkan dulu ke NULL."""
	frappe.db.sql(
		"""
		UPDATE `tabSurat Pengantar Buah`
		SET trans_no = NULL
		WHERE trans_no = ''
		"""
	)
