# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc

class PengeluaranBarang(Document):
	def validate(self):
		self.validate_qty()

	def on_submit(self):
		self.create_ste()
		self.update_items_out()
	
	def on_cancel(self):
		ste = frappe.get_doc("Stock Entry",{"references": self.no_permintaan_pengeluaran})
		ste.cancel()

	def validate_qty(self):
		for row in self.items:
			jumlah_permintaan,jumlah_keluar = frappe.db.get_value("Permintaan Pengeluaran Barang Item",row.reference,["jumlah","jumlah_keluar"])
			qty = row.jumlah - (jumlah_permintaan - jumlah_keluar)
			if qty < 0:
				frappe.throw(f"Jumlah barang melebihi maksimal permintaan: {qty}")

	def update_items_out(self):
		for row in self.items:
			jumlah_keluar = frappe.db.get_value("Permintaan Pengeluaran Barang Item",row.reference,"jumlah_keluar")
			frappe.db.set_value("Permintaan Pengeluaran Barang Item",row.reference,"jumlah_keluar",jumlah_keluar + row.jumlah,update_modified=False)
		
		frappe.get_doc("Permintaan Pengeluaran Barang",self.no_permintaan_pengeluaran).update_status()


	def update_return_percentage(self):
		qty = 0
		return_qty = 0

		for row in self.items:
			qty += row.jumlah
			return_qty += row.jumlah_retur
		
		return_percent = return_qty/qty * 100

		self.db_set("return_percentage",return_percent)

	@frappe.whitelist()
	def set_items(self):
		self.items = []
		if not self.validate_document_permintaan():
			return

		items = frappe.get_all("Permintaan Pengeluaran Barang Item",{"parent":self.no_permintaan_pengeluaran},["kode_barang","satuan","(jumlah - jumlah_keluar) as jumlah","kendaraan","km","kegiatan","sub_unit","blok","name as reference"])

		for row in items:
			self.append("items",row)

	def validate_document_permintaan(self):
		company,status,outgoing = frappe.db.get_value("Permintaan Pengeluaran Barang",self.no_permintaan_pengeluaran, ["pt_pemilik_barang","status","outgoing"])
		if company != self.pt_pemilik_barang or status == "Closed" or outgoing == 100:
			return False
		return True

	def create_ste(self):
		def postprocess(source,target):
			target.stock_entry_type = "Material Issue"
			
			update_fields = (
				"item_name",
				"stock_uom",
				"description",
				"expense_account",
				"cost_center",
				"conversion_factor",
				"barcode",
			)

			for item in target.items:
				item_details = target.get_item_details(
					frappe._dict(
						{
							"item_code": item.item_code,
							"company": target.company,
							"project": target.project,
							"uom": item.uom,
							"s_warehouse": item.s_warehouse,
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
			target.s_warehouse = source_parent.gudang
			

		mapper = {
			"Permintaan Pengeluaran Barang": {
				"doctype": "Stock Entry",
				"field_map": {
					"name":"references",
					"doctype": "reference_doctype",
					"sub_unit":"unit",
					"pt_pemilik_barang":"company",
					"tanggal":"posting_date"
				}
			},

			"Permintaan Pengeluaran Barang Item": {
				"doctype": "Stock Entry Detail",
				"field_map": {
					"kode_barang":"item_code",
					"jumlah": "qty",
					"kendaraan":"custom_alat_berat_dan_kendaraan",
					"satuan": "uom"
				},
				"postprocess": update_item
			}
		}

		doc = get_mapped_doc("Permintaan Pengeluaran Barang",self.no_permintaan_pengeluaran,mapper,None,postprocess,True)
		doc.insert()
		doc.submit()
		
