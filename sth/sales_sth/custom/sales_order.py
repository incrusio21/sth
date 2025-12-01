import frappe

@frappe.whitelist()
def check_dn_pending(self,method):
	customer = self.customer
	check_so = frappe.db.sql(""" SELECT name FROM `tabSales Order` WHERE docstatus = 1 and status != "Closed" and per_delivered < 100 and customer = "{}" """.format(self.customer))
	if len(check_so) > 0:
		
		self.check_dn_pending = 1
	else:
		self.check_dn_pending = 0