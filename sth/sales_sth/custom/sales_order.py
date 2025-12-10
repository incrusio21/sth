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
	return

	# dimatikan dulu
	item_price_list = frappe.db.sql(""" SELECT name, item_code, price_list_rate, allowed_rate_under, allowed_rate_over FROM `tabItem Price` WHERE price_list = "{}" """.format(self.selling_price_list), as_dict=1)

	for row in self.items:
		if row.rate:
			check_price_list = 0
			for satu_item_price in item_price_list:
				if satu_item_price.item_code == row.item_code:
					check_price_list = satu_item_price.price_list_rate
					if row.rate - check_price_list > satu_item_price.allowed_rate_over :
						frappe.throw("Nilai Rate tidak boleh lebih sebanyak {} dari Nilai Price List Rate. Ini ditentukan di Item Price bagian Allowed Price Over.".format(satu_item_price.allowed_rate_over))
					
					if check_price_list - row.rate > satu_item_price.allowed_rate_under :
						frappe.throw("Nilai Rate tidak boleh kurang sebanyak {} dari Nilai Price List Rate. Ini ditentukan di Item Price bagian Allowed Price Under.".format(satu_item_price.allowed_rate_under))
				