import frappe

from sth.buying_sth.custom.ongkos_angkut_transportir import INVOICE_TYPE


def execute():
	"""Tipe invoice untuk tagihan transportir yang ditarik dari nomor Delivery Order."""
	if frappe.db.exists("Purchase Invoice Type", INVOICE_TYPE):
		return

	doc = frappe.new_doc("Purchase Invoice Type")
	doc.document_type = "Delivery Order"
	doc.insert(set_name=INVOICE_TYPE, ignore_permissions=True)
