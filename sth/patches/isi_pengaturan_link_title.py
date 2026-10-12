import frappe


# Yang dulu tertanam di JS doctype masing-masing (material_request.js,
# sales_invoice.js, pertanggungjawaban_perjalanan_dinas.js). None berarti semua
# link di doctype itu menampilkan nama dokumennya.
PENGECUALIAN = [
	("Material Request", "Item"),
	("Sales Invoice", None),
	("Pertanggungjawaban Perjalanan Dinas", None),
]


def execute():
	"""Isi Pengaturan Link Title dari Link Title yang berlaku sekarang.

	Doctype-nya diambil dari Property Setter show_title_field_in_link bernilai 1 —
	yang dinyalakan lewat Customize Form dan bisa hilang — ditambah doctype milik
	sth yang menyalakannya di JSON. Doctype app lain yang menyalakannya di JSON
	(LMS, Insights, Contact, ...) tidak diambil: bawaan app-nya sendiri, tidak
	pernah hilang, dan tetap jalan tanpa master.

	Patch post_model_sync jalan sebelum sync_customizations, jadi yang terbaca di
	sini keadaan site sebelum berkas custom/*.json disinkronkan.

	Master yang sudah berisi dibiarkan, jadi aman diulang.
	"""
	doc = frappe.get_single("Pengaturan Link Title")
	if doc.doctype_link_title or doc.pengecualian:
		return

	dari_property_setter = frappe.get_all(
		"Property Setter",
		filters={
			"property": "show_title_field_in_link",
			"value": "1",
			"doctype_or_field": "DocType",
		},
		pluck="doc_type",
	)
	dari_sth = frappe.get_all(
		"DocType",
		filters={
			"show_title_field_in_link": 1,
			"module": ["in", frappe.get_module_list("sth")],
			"istable": 0,
			"issingle": 0,
		},
		pluck="name",
	)

	for doctype in sorted(set(dari_property_setter + dari_sth)):
		if not frappe.db.exists("DocType", doctype):
			continue

		# Tanpa title field, Link Title-nya memang tidak pernah menampilkan apa-apa,
		# dan baris seperti itu ditolak validate.
		title_field = frappe.get_meta(doctype).title_field
		if not title_field:
			continue

		doc.append(
			"doctype_link_title",
			{"document_type": doctype, "title_field": title_field, "tampilkan": 1},
		)

	for di_doctype, document_type in PENGECUALIAN:
		if frappe.db.exists("DocType", di_doctype):
			doc.append("pengecualian", {"di_doctype": di_doctype, "document_type": document_type})

	doc.save(ignore_permissions=True)
