# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
class BeritaAcara(Document):
	pass

@frappe.whitelist()
def create_mr(source_name,target_doc=None):
	def set_missing_values(source,target):
		target.purchase_type = "Berita Acara"

	mapper = {
		"Berita Acara": {
			"doctype": "Material Request",
			"field_map":{
				"name" : "berita_acara"
			},
			"validation": {
				"docstatus": ["=", 1],
			},
			"conditions": lambda doc: not doc.material_request
		},

		"Berita Acara Detail": {
			"doctype": "Material Request Item",
			"field_map": {
				"jumlah":"qty"
			}
		},
	}

	
	return get_mapped_doc("Berita Acara",source_name,mapper,target_doc,set_missing_values)