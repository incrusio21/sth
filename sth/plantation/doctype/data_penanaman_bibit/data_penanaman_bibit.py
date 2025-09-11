# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.query_builder.functions import Sum

class DataPenanamanBibit(Document):
	def get_available_qty(self):
		data = frappe.get_value(
			"Data Penyemaian Bibit",
			self.data_penyemaian_bibit,
			["transplanting_qty", "planting_qty"],
			as_dict=True,
			for_update=True,
		)

		if data:
			self.available_qty = (data.get("transplanting_qty") or 0) - (data.get("planting_qty") or 0)
		else:
			self.available_qty = 0
	
	def limit_qty(self):
		if(self.available_qty < self.qty):
			frappe.throw(f"Jumlah Bibit must not be greater than Available Qty ({self.available_qty})")
   
		if(self.qty<0):
			frappe.throw(f"Jumlah Bibit must not be less than 0")
  
	def validate(self):
		self.get_available_qty()
		self.limit_qty()

	def recalculate_qty_data_penyemaian_bibit(self):
		dpda = frappe.qb.DocType("Data Penanaman Bibit")

		def get_total():
			return (
				frappe.qb.from_(dpda)
				.select(Sum(dpda.qty))
				.where(
					(dpda.data_penyemaian_bibit == self.data_penyemaian_bibit)
					& (dpda.item_code == self.item_code)
					& (dpda.batch == self.batch)					
					& (dpda.docstatus == 1)
				)
			).run()[0][0] or 0.0

		used_total = get_total()		

		doc = frappe.get_doc("Data Penyemaian Bibit", self.data_penyemaian_bibit)
  
		doc.planting_qty = used_total
		doc.calculate_grand_total_qty()
		doc.db_update()

	def on_submit(self):
		self.recalculate_qty_data_penyemaian_bibit()
	
	def on_cancel(self):
		self.recalculate_qty_data_penyemaian_bibit()
