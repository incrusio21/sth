import frappe

def generate_kriteria_upload_payment(doc, method=None):
	if doc.is_new():
		return
	
	if not doc.references:
		return

	all_rows = []
	seen = set()

	for ref in doc.references:
		print(ref.reference_doctype)
		rows = get_kriteria_rows_for_reference(ref.reference_doctype, ref.reference_name)
		for row in rows:
			# Unique key: kombinasi document_type + document_no + rincian_dokumen_finance + file
			key = (
				row["document_type"],
				row["document_no"],
				row["rincian_dokumen_finance"],
				row["uploaded_file"],
			)
			if key not in seen:
				seen.add(key)
				all_rows.append(row)

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

		for do_name in linked["delivery_orders"]:
			rows.extend(get_file_upload_rows("Delivery Order", do_name))

		rows.extend(get_file_upload_rows("Sales Invoice", reference_name))

	elif reference_doctype == "Purchase Invoice":
		# Special case: pull from Sales Order, Delivery Note, and Sales Invoice itself
		linked = get_purchase_invoice_links(reference_name)

		for po_name in linked["purchase_orders"]:
			rows.extend(get_file_upload_rows("Purchase Order", po_name))

		for pr_name in linked["purchase_receipts"]:
			rows.extend(get_file_upload_rows("Purchase Receipt", pr_name))

		for mr_name in linked["material_requests"]:
			rows.extend(get_file_upload_rows("Material Request", mr_name))

		for sq_name in linked["supplier_quotations"]:
			rows.extend(get_file_upload_rows("Supplier Quotation", sq_name))

		for ba_name in linked["berita_acara"]:
			rows.extend(get_file_upload_rows("Berita Acara", ba_name))

		rows.extend(get_file_upload_rows("Purchase Invoice", reference_name))

	elif reference_doctype == "Employee Advance":
		linked = get_employee_advance_links(reference_name)

		for pp_name in linked["pengajuan_perdins"]:
			rows.extend(get_file_upload_rows("Travel Request", pp_name))

		rows.extend(get_file_upload_rows("Employee Advance", reference_name))

	else:
		rows.extend(get_file_upload_rows(reference_doctype, reference_name))

	return rows

def get_employee_advance_links(employee_advance_name):
	travel_requests = frappe.get_all(
		"Travel Request",
		filters={"custom_employee_advance": employee_advance_name, "docstatus": 1},
		fields=["name"]
	)
	
	pengajuan_perdins = [tr["name"] for tr in travel_requests]
	employee_advances = [employee_advance_name]
	
	return {
		"employee_advances": employee_advances,
		"pengajuan_perdins": pengajuan_perdins
	}

def get_sales_invoice_links(sales_invoice_name):
	# 1. Sales Invoice sendiri
	sales_invoices = [sales_invoice_name]

	# 2. Ambil delivery_note dari Sales Invoice
	si_doc = frappe.get_doc("Sales Invoice", sales_invoice_name)
	delivery_notes = list({row.delivery_note for row in si_doc.items if row.delivery_note})

	# 3. Ambil delivery_order dari Delivery Note
	delivery_orders = []
	for dn_name in delivery_notes:
		dn_doc = frappe.get_doc("Delivery Note", dn_name)
		if dn_doc.delivery_order:
			delivery_orders.append(dn_doc.delivery_order)
	delivery_orders = list(set(delivery_orders))

	# 4. Ambil sales_order dari Delivery Order
	sales_orders = []
	for do_name in delivery_orders:
		do_doc = frappe.get_doc("Delivery Order", do_name)
		if do_doc.sales_order:
			sales_orders.append(do_doc.sales_order)
	sales_orders = list(set(sales_orders))

	return {
		"sales_invoices":  sales_invoices,
		"delivery_notes":  delivery_notes,
		"delivery_orders": delivery_orders,
		"sales_orders":    sales_orders,
	}
	
def get_purchase_invoice_links(purchase_invoice_name):
	purchase_invoices = [purchase_invoice_name]
	# 1. Ambil purchase_receipt dari Purchase Invoice
	pi_doc = frappe.get_doc("Purchase Invoice", purchase_invoice_name)
	purchase_receipts = list({row.purchase_receipt for row in pi_doc.items if row.purchase_receipt})

	# 2. Ambil purchase_order dari Purchase Receipt
	purchase_orders = []
	if purchase_receipts:
		for pr_name in purchase_receipts:
			pr_doc = frappe.get_doc("Purchase Receipt", pr_name)
			for row in pr_doc.items:
				if row.purchase_order:
					purchase_orders.append(row.purchase_order)
		purchase_orders = list(set(purchase_orders))

	# 3. Ambil supplier_quotation dari Purchase Order
	supplier_quotations = []
	if purchase_orders:
		for po_name in purchase_orders:
			po_doc = frappe.get_doc("Purchase Order", po_name)
			for row in po_doc.items:
				if row.supplier_quotation:
					supplier_quotations.append(row.supplier_quotation)
		supplier_quotations = list(set(supplier_quotations))

	# 4. Ambil material_request dari Supplier Quotation
	material_requests = []
	if supplier_quotations:
		for sq_name in supplier_quotations:
			sq_doc = frappe.get_doc("Supplier Quotation", sq_name)
			for row in sq_doc.items:
				if row.material_request:
					material_requests.append(row.material_request)
		material_requests = list(set(material_requests))

	# 5. Ambil berita_acara dari Material Request
	berita_acara_list = []
	if material_requests:
		mr_docs = frappe.get_all(
			"Material Request",
			filters={"name": ["in", material_requests]},
			fields=["name", "berita_acara"]
		)
		berita_acara_list = list({r.berita_acara for r in mr_docs if r.berita_acara})

	return {
		"purchase_invoices":   purchase_invoices,
		"purchase_receipts":   purchase_receipts,
		"purchase_orders":     purchase_orders,
		"supplier_quotations": supplier_quotations,
		"material_requests":   material_requests,
		"berita_acara":        berita_acara_list,
	}

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

	DOC_LABEL = {
		"Sales Order": "Kontrak Penjualan",
		"Delivery Order": "Delivery Order",
		"Delivery Note": "Delivery Note",
		"Sales Invoice": "Pengakuan Penjualan",
		
		"Material Request": "PR/SR",
		"Supplier Quotation": "Supplier Quotation",
		"Purchase Order": "Purchase Order",
		"Purchase Receipt": "Purchase Receipt",
		"Purchase Invoice": "Purchase Invoice",

		"Travel Request": "Pengajuan Perjalanan Dinas"
	}

	for row in doc.file_upload:
		rows.append({
			"doctype":                 "Kriteria Upload Payment Item",  # adjust to your child doctype name
			"document_type":           DOC_LABEL.get(voucher_type,voucher_type),
			"document_no":             voucher_no,
			"rincian_dokumen_finance": row.rincian_dokumen_finance,
			"uploaded_file":           row.upload_file,
		})

	return rows