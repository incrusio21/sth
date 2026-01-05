import frappe
from frappe import _

def populate_upload_file(doc, method=None):
	populate_linked_documents(doc)

def populate_linked_documents(doc):
	all_uploads = []
	processed_docs = set() 
	
	if not doc.references:
		return
	
	for ref in doc.references:
		if ref.reference_doctype == "Sales Invoice" and ref.reference_name:
			collect_uploads_from_chain(
				ref.reference_name, 
				all_uploads, 
				processed_docs
			)
	
	doc.kriteria_upload_dokumen_finance_pe = []
	
	for upload in all_uploads:
		doc.append("kriteria_upload_dokumen_finance_pe", {
			"document_type": upload["document_type"],
			"document_no": upload["document_no"],
			"rincian_dokumen_finance": upload["rincian_dokumen_finance"],
			"uploaded_file": upload["uploaded_file"]
		})

def collect_uploads_from_chain(sales_invoice_name, all_uploads, processed_docs):
	collect_uploads_from_doc(
		"Sales Invoice", 
		sales_invoice_name, 
		all_uploads, 
		processed_docs
	)
	
	linked_docs = get_linked_docs_from_sales_invoice(sales_invoice_name)
	
	for so_name in linked_docs.get("sales_orders", []):
		if so_name not in processed_docs:
			collect_uploads_from_doc(
				"Sales Order", 
				so_name, 
				all_uploads, 
				processed_docs
			)
			
			quotations = get_quotations_from_sales_order(so_name)
			for quot_name in quotations:
				if quot_name not in processed_docs:
					collect_uploads_from_doc(
						"Quotation", 
						quot_name, 
						all_uploads, 
						processed_docs
					)
	
	for dn_name in linked_docs.get("delivery_notes", []):
		if dn_name not in processed_docs:
			collect_uploads_from_doc(
				"Delivery Note", 
				dn_name, 
				all_uploads, 
				processed_docs
			)
			
			sales_orders = get_sales_orders_from_delivery_note(dn_name)
			for so_name in sales_orders:
				if so_name not in processed_docs:
					collect_uploads_from_doc(
						"Sales Order", 
						so_name, 
						all_uploads, 
						processed_docs
					)
					
					quotations = get_quotations_from_sales_order(so_name)
					for quot_name in quotations:
						if quot_name not in processed_docs:
							collect_uploads_from_doc(
								"Quotation", 
								quot_name, 
								all_uploads, 
								processed_docs
							)

def collect_uploads_from_doc(doctype, docname, all_uploads, processed_docs):
	if docname in processed_docs:
		return
	
	processed_docs.add(docname)
	doc = frappe.get_doc(doctype, docname)
	
	if not hasattr(doc, 'kriteria_upload_dokumen_finance'):
		return
	
	for row in doc.kriteria_upload_dokumen_finance:
		all_uploads.append({
			"document_type": doctype, 
			"document_no": docname,
			"rincian_dokumen_finance": row.rincian_dokumen_finance,
			"uploaded_file": row.upload_file
		})

def get_linked_docs_from_sales_invoice(sales_invoice_name):
	items = frappe.get_all(
		"Sales Invoice Item",
		filters={"parent": sales_invoice_name},
		fields=["sales_order", "delivery_note"]
	)
	
	sales_orders = set()
	delivery_notes = set()
	
	for item in items:
		if item.sales_order:
			sales_orders.add(item.sales_order)
		if item.delivery_note:
			delivery_notes.add(item.delivery_note)
	
	return {
		"sales_orders": list(sales_orders),
		"delivery_notes": list(delivery_notes)
	}

def get_quotations_from_sales_order(sales_order_name):
	items = frappe.get_all(
		"Sales Order Item",
		filters={"parent": sales_order_name},
		fields=["prevdoc_docname"]
	)
	
	quotations = set()
	for item in items:
		if item.prevdoc_docname:
			quotations.add(item.prevdoc_docname)
	
	return list(quotations)

def get_sales_orders_from_delivery_note(delivery_note_name):
	items = frappe.get_all(
		"Delivery Note Item",
		filters={"parent": delivery_note_name},
		fields=["against_sales_order"]
	)
	
	sales_orders = set()
	for item in items:
		if item.against_sales_order:
			sales_orders.add(item.against_sales_order)
	
	return list(sales_orders)


# Alternative: More efficient query-based approach
def populate_linked_documents_optimized(doc):
	all_uploads = []
	
	sales_invoices = [
		ref.reference_name 
		for ref in doc.references 
		if ref.reference_doctype == "Sales Invoice" and ref.reference_name
	]
	
	if not sales_invoices:
		doc.kriteria_upload_dokumen_finance_pe = []
		return
	
	document_chain = build_document_chain_sql(sales_invoices)
	
	for doctype, docnames in document_chain.items():
		if docnames:
			uploads = get_uploads_from_documents(doctype, docnames)
			all_uploads.extend(uploads)
	
	doc.kriteria_upload_dokumen_finance_pe = []
	for upload in all_uploads:
		doc.append("kriteria_upload_dokumen_finance_pe", upload)

def build_document_chain_sql(sales_invoices):
	chain = {
		"Sales Invoice": sales_invoices,
		"Sales Order": [],
		"Delivery Note": [],
		"Quotation": []
	}
	
	si_links = frappe.db.sql("""
		SELECT DISTINCT 
			sales_order, 
			delivery_note
		FROM `tabSales Invoice Item`
		WHERE parent IN %(invoices)s
			AND (sales_order IS NOT NULL OR delivery_note IS NOT NULL)
	""", {"invoices": sales_invoices}, as_dict=1)
	
	for link in si_links:
		if link.sales_order:
			chain["Sales Order"].append(link.sales_order)
		if link.delivery_note:
			chain["Delivery Note"].append(link.delivery_note)
	
	if chain["Delivery Note"]:
		dn_so = frappe.db.sql("""
			SELECT DISTINCT against_sales_order
			FROM `tabDelivery Note Item`
			WHERE parent IN %(dn)s
				AND against_sales_order IS NOT NULL
		""", {"dn": chain["Delivery Note"]}, as_dict=1)
		
		for row in dn_so:
			if row.against_sales_order not in chain["Sales Order"]:
				chain["Sales Order"].append(row.against_sales_order)
				
	if chain["Sales Order"]:
		so_quot = frappe.db.sql("""
			SELECT DISTINCT prevdoc_docname
			FROM `tabSales Order Item`
			WHERE parent IN %(so)s
				AND prevdoc_docname IS NOT NULL
		""", {"so": chain["Sales Order"]}, as_dict=1)
		
		for row in so_quot:
			if row.prevdoc_docname:
				chain["Quotation"].append(row.prevdoc_docname)
	
	return chain

def get_uploads_from_documents(doctype, docnames):
	doctype_map = {
		"Sales Invoice": "Sales Invoice",
		"Sales Order": "Sales Order",
		"Delivery Note": "Delivery Note",
		"Quotation": "Quotation"
	}
	
	uploads = frappe.db.sql("""
		SELECT 
			parent as document_no,
			rincian_dokumen_finance,
			upload_file as uploaded_file
		FROM `tabKriteria Upload Dokumen Finance`
		WHERE parent IN %(docs)s
			AND parenttype = %(doctype)s
			AND upload_file IS NOT NULL
			AND upload_file != ''
		ORDER BY parent, idx
	""", {"docs": docnames, "doctype": doctype_map[doctype]}, as_dict=1)
	
	return uploads