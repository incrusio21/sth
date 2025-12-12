import frappe,copy
from frappe.utils import flt,today,add_days
from frappe.model.mapper import get_mapped_doc

@frappe.whitelist()
def make_purchase_order(source_name, target_doc=None):
	def set_missing_values(source, target):
		target.run_method("set_missing_values")
		target.run_method("get_schedule_dates")
		target.run_method("calculate_taxes_and_totals")
		
		data_type = frappe.db.get_value("Material Request",source.custom_material_request,["purchase_type","sub_purchase_type"],as_dict=True)

		if getattr(data_type,"purchase_type",None) == "Berita Acara":
			target.purchase_type = "Non Capex"
			target.sub_purchase_type = data_type.sub_purchase_type

		tax_template_name = frappe.get_value("Purchase Taxes and Charges Template",{"title":"STH TAX AND CHARGE", "company":target.company}, pluck="name") or ""
		target.taxes_and_charges = tax_template_name

		list_taxes = [r.account_head for r in target.taxes]
		unassign_tax = fetch_unassigned_taxes(tax_template_name,list_taxes)
		for data in unassign_tax:
			tax = target.append('taxes')
			tax.update(data)

		for row in target.items:
			row.schedule_date = source.custom_required_by or add_days(today(),7)

	def update_item(obj, target, source_parent):
		target.stock_qty = flt(obj.qty) * flt(obj.conversion_factor)

	doclist = get_mapped_doc(
		"Supplier Quotation",
		source_name,
		{
			"Supplier Quotation": {
				"doctype": "Purchase Order",
				"field_map": {
					"custom_required_by":"schedule_date"
				},
				"field_no_map": ["transaction_date"],
				"validation": {
					"docstatus": ["=", 1],
				},
			},
			"Supplier Quotation Item": {
				"doctype": "Purchase Order Item",
				"field_map": [
					["name", "supplier_quotation_item"],
					["parent", "supplier_quotation"],
					["material_request", "material_request"],
					["material_request_item", "material_request_item"],
					["sales_order", "sales_order"],
				],
				"postprocess": update_item,
			},
			"Purchase Taxes and Charges": {
				"doctype": "Purchase Taxes and Charges",
			},
		},
		target_doc,
		set_missing_values,
	)

	return doclist

def fetch_unassigned_taxes(template_name,list_taxes):
	# mencari taxes yang belum dimasukkan pada suatu reference template
	param = [template_name]
	additional = ""
	
	query = frappe.db.sql(f"""
		select ptc.charge_type,ptc.account_head,ptc.description,ptc.rate,ptc.tax_amount, ptc.category, ptc.add_deduct_tax,ptc.row_id
		from `tabPurchase Taxes and Charges` ptc
		join `tabPurchase Taxes and Charges Template` ptt on ptt.name = ptc.parent
		where ptt.name = %s {additional}
		order by ptc.idx
	""",param,as_dict=True)

	if list_taxes:
		additional = "and ptc.account_head not in %s"
		param.append(list_taxes)

	return query