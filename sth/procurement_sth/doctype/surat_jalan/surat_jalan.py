# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc


class SuratJalan(Document):
	def on_submit(self):
		self.create_ste()
	
	def on_cancel(self):
		ste = frappe.get_doc("Stock Entry",{"references": self.name})
		ste.cancel()

	def create_ste(self):
		def postprocess(source,target):
			target.stock_entry_type = "Material Transfer"

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
			target.s_warehouse = source_parent.gudang_asal
			target.t_warehouse = source_parent.gudang_tujuan
			

		mapper = {
			"Surat Jalan": {
				"doctype": "Stock Entry",
				"field_map": {
					"name":"references",
					"doctype": "reference_doctype",
					"tanggal_kirim": "posting_date"
				}
			},

			"Surat Jalan Item": {
				"doctype": "Stock Entry Detail",
				"field_map": {
					"kode_barang":"item_code",
					"jumlah": "qty",
					"satuan": "uom"
				},
				"postprocess": update_item
			}
		}

		doc = get_mapped_doc("Surat Jalan",self.name,mapper,None,postprocess,True)
		doc.insert()
		doc.submit()

@frappe.whitelist()
def get_items_from_po(doctype):
	pass


@frappe.whitelist()
def get_stock_item(item_code,warehouse):
	return frappe.db.sql("""
		select i.item_code, i.item_name, sum(b.actual_qty) as stock, i.stock_uom as uom 
		from `tabBin` b
		join `tabItem` i on i.name = b.item_code
		where b.warehouse = %s and i.item_code = %s
		group by i.item_code
	""",[warehouse,item_code],as_dict=True)