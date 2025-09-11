# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt
from frappe.model.document import Document
from frappe.query_builder.functions import Sum


class DataPencatatanDobletoneDanAfkir(Document):
	def limit_qty(self):
		if(self.data_pencatatan_type == "Afkir" and self.available_qty <= 0):
			frappe.throw(f"Available Qty is not enough.")
   
		if(self.available_qty<self.qty):
			frappe.throw(f"Jumlah Bibit must not be greater than Available Qty ({self.available_qty})")
   
		if(self.qty<0):
			frappe.throw(f"Jumlah Bibit must not be less than 0")	
   
	def validate_used_qty(self):
		if(self.data_pencatatan_type=="Afkir"):
			temp = self.available_qty-self.qty
			if(temp<0):
				frappe.throw(f"Acumulate Available Qty - Jumlah Bibit cant be less than {self.available_qty}")

	def validate(self):
		self.limit_qty()
	
	def recalculate_qty_data_penyemaian_bibit(self):
		dpda = frappe.qb.DocType("Data Pencatatan Dobletone Dan Afkir")

		def get_total(pencatatan_type):
			return (
				frappe.qb.from_(dpda)
				.select(Sum(dpda.qty))
				.where(
					(dpda.data_penyemaian_bibit == self.data_penyemaian_bibit)
					& (dpda.item_code == self.item_code)
					& (dpda.batch == self.batch)					
					& (dpda.docstatus == 1)
					& (dpda.data_pencatatan_type == pencatatan_type)
				)
			).run()[0][0] or 0.0

		used_total_dobletone = get_total("Dobletone")
		used_total_afkir = get_total("Afkir")

		doc = frappe.get_doc("Data Penyemaian Bibit", self.data_penyemaian_bibit)
  
		doc.qty_dobletone = used_total_dobletone
		doc.qty_after_afkir = used_total_afkir
		doc.calculate_grand_total_qty()
		doc.db_update()

	def on_submit(self):
		self.validate_used_qty()
		self.recalculate_qty_data_penyemaian_bibit()
	
	def on_cancel(self):
		self.recalculate_qty_data_penyemaian_bibit()