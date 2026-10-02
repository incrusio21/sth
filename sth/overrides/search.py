import frappe
from frappe.desk.search import get_link_title as frappe_get_link_title

@frappe.whitelist()
def get_link_title(doctype, docname):
	return frappe_get_link_title(doctype, docname)