# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc

class ReturKeGudang(Document):
	def validate(self):
		self.validate_qty()

	def on_submit(self):
		self.create_ste()
		self.update_items_return(method="submit")
	
	def on_cancel(self):
		ste = frappe.get_doc("Stock Entry",{"references": self.name})
		self.update_items_return(method="cancel")
		ste.cancel()


	def validate_qty(self):
		for row in self.items:
			if row.jumlah > row.jumlah_maksimal:
				frappe.throw(f"Jumlah barang melebihi maksimal yang dikembalikan")

	def update_items_return(self,method):
		for row in self.items:
			jumlah_retur = frappe.db.get_value("Pengeluaran Barang Item",row.reference,"jumlah_retur")
			
			jumlah_retur = jumlah_retur + row.jumlah if method == "submit" else jumlah_retur - row.jumlah
			frappe.db.set_value("Pengeluaran Barang Item",row.reference,"jumlah_retur",jumlah_retur,update_modified=False)
		
		frappe.get_doc("Pengeluaran Barang",self.no_pengeluaran).update_return_percentage()

	@frappe.whitelist()
	def set_items(self):
		self.items = []
		items = frappe.get_all("Pengeluaran Barang Item",{"parent":self.no_pengeluaran},["kode_barang","satuan","(jumlah - jumlah_retur) as jumlah","(jumlah - jumlah_retur) as jumlah_maksimal","blok as kode_blok","name as reference"])

		for row in items:
			child = self.append("items",row)
			child.nama_barang = frappe.db.get_value("Item",row.kode_barang,"item_name")

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
