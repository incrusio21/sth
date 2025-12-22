# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc

class ReturKeGudang(Document):
	def on_submit(self):
		self.create_ste()
	
	def on_cancel(self):
		ste = frappe.get_doc("Stock Entry",{"references": self.name})
		ste.cancel()

	def create_ste(self):
		def postprocess(source,target):
			target.stock_entry_type = "Material Receipt"

			update_fields = (
				"item_name",
				"stock_uom",
				"description",
				"expense_account",
				"cost_center",
				"conversion_factor",
				"barcode",
				"basic_rate"
			)

			for item in target.items:
				item_details = target.get_item_details(
					frappe._dict(
						{
							"item_code": item.item_code,
							"company": target.company,
							"project": target.project,
							"uom": item.uom,
						}
					),
					for_update=True,
				)

				for field in update_fields:
					if not item.get(field):
						item.set(field, item_details.get(field))
					if field == "conversion_factor" and item.uom == item_details.get("stock_uom"):
						item.set(field, item_details.get(field))

			target.run_method("set_missing_values")


		def update_item(source,target,source_parent):
			target.t_warehouse = source_parent.gudang
			

		mapper = {
			"Retur Ke Gudang": {
				"doctype": "Stock Entry",
				"field_map": {
					"name":"references",
					"doctype": "reference_doctype",
					"pemilik":"company",
					"tanggal": "posting_date"
				}
			},

			"Retur Items": {
				"doctype": "Stock Entry Detail",
				"field_map": {
					"kode_barang":"item_code",
					"nama_barang":"item_name",
					"jumlah": "qty",
					"satuan": "uom"
				},
				"postprocess": update_item
			}
		}

		doc = get_mapped_doc("Retur Ke Gudang",self.name,mapper,None,postprocess,True)
		doc.insert()
		doc.submit()
