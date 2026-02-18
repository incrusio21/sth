import frappe

def generate_kriteria_upload_payment(doc, method=None):
	if doc.is_new():
		return
	
	if not doc.references:
		return

	all_rows = []

	for ref in doc.references:
		rows = get_kriteria_rows_for_reference(ref.reference_doctype, ref.reference_name)
		all_rows.extend(rows)

	if not all_rows:
		return  

	existing = frappe.db.get_value(
		"Kriteria Upload Payment",
		{"voucher_type": "Payment Entry", "voucher_no": doc.name},
		"name"
	)

	if existing:
		kup = frappe.get_doc("Kriteria Upload Payment", existing)
		kup.file_upload = []
		for row in all_rows:
			kup.append("file_upload", row)
		kup.save(ignore_permissions=True)
	else:
		kup = frappe.new_doc("Kriteria Upload Payment")
		kup.voucher_type = "Payment Entry"
		kup.voucher_no   = doc.name
		for row in all_rows:
			kup.append("file_upload", row)
		kup.insert(ignore_permissions=True)

	frappe.db.commit()


def get_kriteria_rows_for_reference(reference_doctype, reference_name):
	rows = []

	if reference_doctype == "Sales Invoice":
		# Special case: pull from Sales Order, Delivery Note, and Sales Invoice itself
		linked = get_sales_invoice_links(reference_name)

		for so_name in linked["sales_orders"]:
			rows.extend(get_file_upload_rows("Sales Order", so_name))

		for dn_name in linked["delivery_notes"]:
			rows.extend(get_file_upload_rows("Delivery Note", dn_name))

		rows.extend(get_file_upload_rows("Sales Invoice", reference_name))

	else:
		rows.extend(get_file_upload_rows(reference_doctype, reference_name))

	return rows


def get_sales_invoice_links(sales_invoice_name):
	"""
	Get unique Sales Orders and Delivery Notes linked to a Sales Invoice
	via its items table.
	"""
	si_items = frappe.get_all(
		"Sales Invoice Item",
		filters={"parent": sales_invoice_name},
		fields=["sales_order", "delivery_note"]
	)

	sales_orders   = list({r.sales_order   for r in si_items if r.sales_order})
	delivery_notes = list({r.delivery_note for r in si_items if r.delivery_note})

	return {"sales_orders": sales_orders, "delivery_notes": delivery_notes}


def get_file_upload_rows(voucher_type, voucher_no):
	"""
	Find the Kriteria Upload Document for a given voucher_type + voucher_no
	and return its file_upload rows mapped to Kriteria Upload Payment structure.
	"""
	doc_name = frappe.db.get_value(
		"Kriteria Upload Document",
		{"voucher_type": voucher_type, "voucher_no": voucher_no},
		"name"
	)

	if not doc_name:
		return []

	doc  = frappe.get_doc("Kriteria Upload Document", doc_name)
	rows = []

	for row in doc.file_upload:
		rows.append({
			"doctype":                 "Kriteria Upload Payment Item",  # adjust to your child doctype name
			"document_type":           voucher_type,
			"document_no":             voucher_no,
			"rincian_dokumen_finance": row.rincian_dokumen_finance,
			"uploaded_file":           row.upload_file,
		})

	return rows