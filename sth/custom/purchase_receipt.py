import frappe

@frappe.whitelist()
def set_purchase_order_if_exist(doc,method):
	if not doc.purchase_order:
		if doc.items[0].purchase_order:
			doc.purchase_order = doc.items[0].purchase_order
