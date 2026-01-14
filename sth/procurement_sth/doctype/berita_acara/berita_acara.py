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
			}
		},
	}

	return get_mapped_doc("Berita Acara",source_name,mapper,target_doc,postprocess)