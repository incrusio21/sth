import frappe

@frappe.whitelist()
def check_dn_pending(self,method):
	if self.docstatus != 0:
		return

	customer = self.customer
	check_so = frappe.db.sql(""" SELECT name FROM `tabSales Order` WHERE docstatus = 1 and status != "Closed" and per_delivered < 100 and customer = "{}" and name != "{}" """.format(self.customer, self.name))
	if len(check_so) > 0:
		self.check_dn_pending = 1
	else:
		self.check_dn_pending = 0

	check_si = frappe.db.sql(""" SELECT name FROM `tabSales Invoice` WHERE docstatus = 1 and status != "Closed" and outstanding_amount > 0 and customer = "{}" """.format(self.customer))
	if len(check_si) > 0:
		self.check_si_pending = 1
	else:
		self.check_si_pending = 0

@frappe.whitelist()
def validate_price_list(self,method):
	for row in self.items:
		if row.rate and row.price_list_rate and row.price_list_rate != 0:
			if abs(row.rate - row.price_list_rate) > 5:
				frappe.throw("Nilai Rate tidak boleh lebih dari / kurang dari 5 dari Nilai Price List Rate")
				