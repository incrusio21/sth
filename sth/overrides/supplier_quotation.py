import frappe,copy
from frappe import _
from frappe.utils import flt,today,add_days
from frappe.model.mapper import get_mapped_doc
from erpnext.buying.doctype.supplier_quotation.supplier_quotation import SupplierQuotation

class STHSupplierQuotation(SupplierQuotation):
	def update_rfq_supplier_status(self, include_me):
		rfq_list = set([])
		for item in self.items:
			if item.request_for_quotation:
				rfq_list.add(item.request_for_quotation)
		for rfq in rfq_list:
			doc = frappe.get_doc("Request for Quotation", rfq)
			doc_sup = frappe.get_all(
				"Request for Quotation Supplier",
				filters={"parent": doc.name, "supplier": self.supplier},
				fields=["name", "quote_status"],
			)

			doc_sup = doc_sup[0] if doc_sup else None
			if not doc_sup:
				# return jika supplier tidak terdaftar
				continue
				# frappe.throw(
				# 	_("Supplier {0} not found in {1}").format(
				# 		self.supplier,
				# 		"<a href='desk/app/Form/Request for Quotation/{0}'> Request for Quotation {0} </a>".format(
				# 			doc.name
				# 		),
				# 	)
				# )

			quote_status = _("Received")
			for item in doc.items:
				sqi_count = frappe.db.sql(
					"""
					SELECT
						COUNT(sqi.name) as count
					FROM
						`tabSupplier Quotation Item` as sqi,
						`tabSupplier Quotation` as sq
					WHERE sq.supplier = %(supplier)s
						AND sqi.docstatus = 1
						AND sq.name != %(me)s
						AND sqi.request_for_quotation_item = %(rqi)s
						AND sqi.parent = sq.name""",
					{"supplier": self.supplier, "rqi": item.name, "me": self.name},
					as_dict=1,
				)[0]
				self_count = (
					sum(my_item.request_for_quotation_item == item.name for my_item in self.items)
					if include_me
					else 0
				)
				if (sqi_count.count + self_count) == 0:
					quote_status = _("Pending")

				frappe.db.set_value(
					"Request for Quotation Supplier", doc_sup.name, "quote_status", quote_status
				)




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