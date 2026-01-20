import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc

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

def track_insurance_changes(doc):
	insurance_fields = [
		'policy_number',
		'insurer', 
		'insured_value',
		'insurance_start_date',
		'insurance_end_date',
		'comprehensive_insurance'
	]
	
	should_create_history = False
	if doc.is_new():
		has_insurance_data = any(doc.get(field) for field in insurance_fields)
		if has_insurance_data:
			should_create_history = True
	else:
		old_doc = doc.get_doc_before_save()
		if old_doc:
			has_changes = any(
				doc.get(field) != old_doc.get(field) 
				for field in insurance_fields
			)
			if has_changes:
				should_create_history = True
	
	if should_create_history:
		doc.append('insurance_history', {
			'policy_number': doc.policy_number,
			'insurer': doc.insurer,
			'insured_value': doc.insured_value,
			'insurance_start_date': doc.insurance_start_date,
			'insurance_end_date': doc.insurance_end_date,
			'comprehensive_insurance': doc.comprehensive_insurance,
			'changed_on': frappe.utils.now(),
			'changed_by': frappe.session.user
		})

@frappe.whitelist()
def make_delivery_order(source_name, target_doc=None):

	def set_missing_values(source, target):
		target.run_method("set_missing_values")
		# target.run_method("calculate_taxes_and_totals")

	def update_item(source, target, source_parent):

		target.sales_order = source_parent.name
		target.sales_order_item = source.name
		
		if source.warehouse:
			target.warehouse = source.warehouse

	doclist = get_mapped_doc("Sales Order", source_name, {
		"Sales Order": {
			"doctype": "Delivery Order",
			"field_map": {
				"name": "sales_order",
				"customer": "customer",
				"customer_name": "customer_name",
				"set_warehouse": "set_warehouse",
				"posting_date": "posting_date",
				"company": "company"
			},
			"validation": {
				"docstatus": ["=", 1]
			}
		},
		"Sales Order Item": {
			"doctype": "Delivery Order Item",
			"field_map": {
				"name": "sales_order_item",
				"parent": "sales_order",
				"rate": "rate",
				"warehouse": "warehouse"
			},
			"postprocess": update_item,
			"condition": lambda doc: doc.delivered_qty < doc.qty
		}
	}, target_doc, set_missing_values)

	return doclist
