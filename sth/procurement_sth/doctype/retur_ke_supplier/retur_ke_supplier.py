# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_return
from frappe.model.document import Document
from sth.controllers.queries import get_fields,get_filters_cond

class ReturKeSupplier(Document):
	def validate(self):
		self.validate_qty()
		self.validate_status_prec()

	def before_submit(self):
		self.create_purchase_return()

	def on_cancel(self):
		self.cancel_all_prec_return()

	@frappe.whitelist()
	def get_data(self):
		self.items = []
		self.validate_status_prec()
		prec = frappe.get_doc("Purchase Receipt",self.no_dokumen_penerimaan)
		self.nama_supplier = frappe.get_cached_value("Supplier",prec.supplier,"supplier_name")
		for item in prec.items:
			child_item = self.append("items")
			child_item.kode_barang = item.item_code
			child_item.nama_barang = item.item_name
			child_item.jumlah_penerimaan = item.qty
			child_item.jumlah = item.qty - item.returned_qty
			child_item.satuan = item.uom


	def validate_status_prec(self):
		if frappe.db.get_value("Purchase Receipt",{"name": self.no_dokumen_penerimaan},"status") in ["Return","Return Issued"]:
			frappe.throw(f"Document {self.no_dokumen_penerimaan} cannot be return")

	def validate_qty(self):
		for row in self.items:
			if row.jumlah == 0:
				frappe.throw(f"Jumlah return barang {row.kode_barang} tidak boleh 0")

			if row.jumlah_penerimaan < row.jumlah:
				frappe.throw(f"Jumlah return barang {row.kode_barang} melebihi penerimaan")

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
		frappe.flags.skip_validate_file = 1
		doc.save()
		doc.submit()
		self.prec_reference = doc.name if not self.prec_reference else self.prec_reference + f",{doc.name}"
	
	def cancel_all_prec_return(self):
		if not self.prec_reference:
			return

		for prec_name in self.prec_reference.split(","):
			doc = frappe.get_doc("Purchase Receipt",prec_name)
			doc.cancel()


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def purchase_receipt_query(doctype, txt, searchfield, start, page_len, filters):
	conditions = []
	fields = ", ".join(get_fields(doctype, ["name"]))
	fcond = get_filters_cond(doctype, filters, conditions) if filters else ""
	return frappe.db.sql(
		f"""
			select {fields} from `tabPurchase Receipt`
			where `tabPurchase Receipt`.{searchfield} like %(txt)s {fcond}
			order by
				(case when locate(%(_txt)s, `tabPurchase Receipt`.name) > 0 then locate(%(_txt)s, `tabPurchase Receipt`.name) else 99999 end),
				`tabPurchase Receipt`.posting_date desc,`tabPurchase Receipt`.posting_time desc,`tabPurchase Receipt`.name desc
			limit %(page_len)s offset %(start)s
		""",
		{"txt": "%%%s%%" % txt, "_txt": txt.replace("%", ""), "start": start, "page_len": page_len}
	)