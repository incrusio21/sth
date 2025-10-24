# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt
from frappe.query_builder.functions import Sum

from sth.controllers.status_updater import StatusUpdater

class DataPenyemaianBibit(StatusUpdater):
	
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.status_updater = [
			{
				"target_dt": "Purchase Receipt Item",
				"join_field": "purchase_receipt_item",
				"target_field": "penyemaian_qty",
				"target_parent_dt": "Purchase Receipt",
				"target_parent_field": "per_penyemaian",
				"target_ref_field": "qty",
				"source_field": "qty_planting",
				"percent_join_field_parent": "voucher_no",
				"no_allowance": True,
				"is_child": False
			},
		]

	
	def validate(self):
		self.check_missing_value()
		self.limit_qty()
		self.calculate_grand_total_qty()
	
	def check_missing_value(self):
		if not self.item_code or not self.batch:
			frappe.throw(f"Item Code, Batch cant be empty.")

		if not self.qty_planting:
			frappe.throw(f"Qty Planting cant be zero.")

	def limit_qty(self):
		if self.qty_planting < self.qty_before_afkir:
			frappe.throw(f"Qty Seed Afkir cant be greather than Qty Planting.")
   
	def calculate_grand_total_qty(self):
		self.calculate_qty_dobletone_and_afkir()

		self.qty = flt(self.qty_planting - self.qty_before_afkir + self.qty_dobletone - self.qty_after_afkir)

	def calculate_qty_dobletone_and_afkir(self):
		dpda = frappe.qb.DocType("Data Pencatatan Dobletone Dan Afkir")

		def get_total(pencatatan_type):
			return (
				frappe.qb.from_(dpda)
				.select(Sum(dpda.qty))
				.where(
					(dpda.data_penyemaian_bibit == self.name)
					& (dpda.item_code == self.item_code)
					& (dpda.batch == self.batch)					
					& (dpda.docstatus == 1)
					& (dpda.data_pencatatan_type == pencatatan_type)
				)
			).run()[0][0] or 0.0

		self.qty_dobletone = get_total("Dobletone")
		self.qty_after_afkir = get_total("Afkir")

	def on_submit(self):
		self.update_prevdoc_status()
		self.make_ste_issue()

	def make_ste_issue(self):		
		doc = frappe.new_doc("Stock Entry")
		doc.stock_entry_type = 'Material Issue'
		doc.company = self.company

		doc.set_posting_time = 1
		doc.posting_date = self.posting_date
		doc.posting_time = self.posting_time
  
		warehouse = frappe.db.get_value(
			"Purchase Receipt Item",
			{
				"parent": self.voucher_no,
				"item_code": self.item_code,
				"batch_no": self.batch
			},
			"warehouse"
		)
		doc.from_warehouse = warehouse
  
		doc.append("items", {			
			"item_code": self.item_code,
			"qty": self.qty,
			"use_serial_batch_fields": 1,
			"batch_no": self.batch
		})
		
		doc.submit()

		self.db_set("stock_entry", doc.name)
		self.db_set("amount", doc.total_outgoing_value)

	def on_cancel(self):
		self.update_prevdoc_status()
		self.cancel_or_remove_ste()

	def after_delete(self):
		self.cancel_or_remove_ste(delete=1)

	def cancel_or_remove_ste(self, delete=0):
		if not self.stock_entry:
			return
		
		doc = frappe.get_doc("Stock Entry", self.stock_entry)
		if doc.docstatus == 1:
			doc.cancel()
		
		if delete:
			doc.delete()

@frappe.whitelist()
def select_purchase_receipt_item(voucher_no):
	prec = frappe.qb.DocType("Purchase Receipt Item")

	return (
		frappe.qb.from_(prec)
		.select(
			prec.name.as_("detail_name"), 
			prec.item_code,
			prec.batch_no,
			Sum(prec.qty - prec.penyemaian_qty).as_("remaining_qty"),
		)
		.where(prec.parent == voucher_no)
	).run(as_dict=1)