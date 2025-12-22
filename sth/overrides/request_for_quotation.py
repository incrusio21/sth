import frappe
from erpnext.accounts.party import get_party_account_currency, get_party_details
from frappe.model.mapper import get_mapped_doc
from erpnext.stock.doctype.material_request.material_request import set_missing_values

@frappe.whitelist()
def make_supplier_quotation_from_rfq(source_name, target_doc=None, for_supplier=None):
	def postprocess(source, target_doc):
		if for_supplier:
			target_doc.supplier = for_supplier
			args = get_party_details(for_supplier, party_type="Supplier", ignore_permissions=True)
			target_doc.currency = args.currency or get_party_account_currency(
				"Supplier", for_supplier, source.company
			)
			target_doc.buying_price_list = args.buying_price_list or frappe.db.get_value(
				"Buying Settings", None, "buying_price_list"
			)
		target_doc.custom_material_request = getattr(source.items[0],"material_request","")
		set_missing_values(source, target_doc)

	doclist = get_mapped_doc(
		"Request for Quotation",
		source_name,
		{
			"Request for Quotation": {
				"doctype": "Supplier Quotation",
				"validation": {"docstatus": ["=", 1]},
				"field_map": {"opportunity": "opportunity"},
			},
			"Request for Quotation Item": {
				"doctype": "Supplier Quotation Item",
				"field_map": {
					"name": "request_for_quotation_item",
					"parent": "request_for_quotation",
					"project_name": "project",
				},
			},
		},
		target_doc,
		postprocess,
	)

	return doclist