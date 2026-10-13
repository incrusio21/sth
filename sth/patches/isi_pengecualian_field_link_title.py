import frappe


# Field yang dulu dipaksa tampil kode lewat tanpa_judul_link / is_title_link di
# JS doctype-nya. Supplier di Purchase Order sengaja tidak ikut: diminta tampil
# nama begitu tidak ada barisnya di master.
FIELD_KODE = [
	("Purchase Invoice", "Supplier", "supplier"),
	("Purchase Receipt", "Supplier", "supplier"),
	("Proposal", "Supplier", "supplier"),
	("Salary Slip", "Employee", "employee"),
	("Rencana Kerja Harian", "Employee", "nik_penerima_material"),
]


def execute():
	"""Pindahkan pengecualian per field dari JS doctype ke Pengaturan Link Title.

	Baris yang sudah ada — untuk field itu, untuk doctype tujuannya tanpa field,
	atau untuk semua link — dilewati, jadi aman diulang.
	"""
	doc = frappe.get_single("Pengaturan Link Title")
	sudah = {(d.di_doctype, d.document_type or "", d.fieldname or "") for d in doc.pengecualian}

	tambah = False
	for di_doctype, document_type, fieldname in FIELD_KODE:
		if {
			(di_doctype, document_type, fieldname),
			(di_doctype, document_type, ""),
			(di_doctype, "", ""),
		} & sudah:
			continue
		if not frappe.db.exists("DocType", di_doctype):
			continue

		doc.append(
			"pengecualian",
			{"di_doctype": di_doctype, "document_type": document_type, "fieldname": fieldname},
		)
		tambah = True

	if tambah:
		doc.save(ignore_permissions=True)
