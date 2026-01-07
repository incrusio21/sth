import frappe

@frappe.whitelist()
def update_print_counter(doctype,docname,val):
    frappe.db.set_value(doctype,docname,"print_counter",val)