# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc

class BeritaAcara(Document):
	pass

@frappe.whitelist()
def create_mr(source_name,target_doc=None):
	def postprocess(source,target):
		target.purchase_type = "Berita Acara"
		target.company = frappe.db.get_value("Unit",target.unit,["company"])
	
	def update_item(source,target,source_parent):
		target.stock = get_stock_item(target.item_code,source_parent.unit)

	mapper = {
		"Berita Acara": {
			"doctype": "Material Request",
			"field_map": {
				"name":"berita_acara"
			}
		},

		"Berita Acara Detail": {
			"doctype": "Material Request Item",
			"field_map": {
				"jumlah": "qty",
				"km_hm": "custom_kmhm",
				"satuan": "uom",
				"note": "description"
			},
			"postprocess": update_item
		},
	}

	return get_mapped_doc("Berita Acara",source_name,mapper,target_doc,postprocess)

@frappe.whitelist()
def get_stock_item(item_code,unit):
	central_warehouse = frappe.db.get_value("Warehouse",{"unit": unit,"central": 1})
	return frappe.db.get_value("Bin",{"item_code":item_code,"warehouse":central_warehouse},["actual_qty"]) or 0