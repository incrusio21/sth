# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_return
from frappe.model.document import Document


class ReturKeSupplier(Document):
	def validate(self):
		self.validate_status_prec()

	def before_submit(self):
		self.create_purchase_return()

	def on_cancel(self):
		self.cancel_all_prec_return()

	@frappe.whitelist()
	def get_items(self):
		self.items = []
		self.validate_status_prec()

		prec_items = frappe.get_doc("Purchase Receipt",self.no_dokumen_penerimaan).items
		for item in prec_items:
			child_item = self.append("items")
			child_item.kode_barang = item.item_code
			child_item.nama_barang = item.item_name
			child_item.jumlah = item.qty - item.returned_qty
			child_item.satuan = item.uom


	def validate_status_prec(self):
		if frappe.db.get_value("Purchase Receipt",{"name": self.no_dokumen_penerimaan},"status") in ["Return","Return Issued"]:
			frappe.throw(f"Document {self.no_dokumen_penerimaan} cannot be return")

	def create_purchase_return(self):
		mapping_qty_items = { r.kode_barang: r.jumlah for r in self.items }

		doc = make_purchase_return(self.no_dokumen_penerimaan)
		deleted_items = []

		for item in doc.items:
			# for testing_purpose, bisa dihapus
			# item.expense_account = frappe.get_value("Company",doc.company,"stock_adjustment_account")

			if hasattr(mapping_qty_items,item.item_code):
				item.qty = getattr(mapping_qty_items,item.item_code,0) * -1
				item.received_qty = item.qty
				item.received_stock_qty = item.qty
			else:
				deleted_items.append(item.name)
		
		# sync item prec
		doc.items = [ r for r in doc.items if r not in deleted_items ]
		doc.save()
		doc.submit()
		self.prec_reference = doc.name if not self.prec_reference else self.prec_reference + f",{doc.name}"
	
	def cancel_all_prec_return(self):
		if not self.prec_reference:
			return

		for prec_name in self.prec_reference.split(","):
			doc = frappe.get_doc("Purchase Receipt",prec_name)
			doc.cancel()