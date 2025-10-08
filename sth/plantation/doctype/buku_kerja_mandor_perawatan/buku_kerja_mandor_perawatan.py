# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe

from frappe.utils import flt
from sth.controllers.buku_kerja_mandor import BukuKerjaMandorController

class BukuKerjaMandorPerawatan(BukuKerjaMandorController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.skip_calculate_supervisi = True
		self.fieldname_total.extend([
			"qty", "hasil"
		])

	def update_rate_or_qty_value(self, item, precision):
		if item.parentfield != "hasil_kerja":
			return
		
		item.qty = flt(item.hasil / self.volume_basis)
		item.rate = item.get("rate") or self.rupiah_basis
		if self.persentase_premi and item.hari_kerja > flt(self.volume_basis * ((1 + self.persentase_premi) / 100)):
			item.premi = self.rupiah_premi

	def after_calculate_item_values(self, table_fieldname, options, total):
		if table_fieldname == "hasil_kerja":
			self.hari_kerja_total = flt(total["hasil"])
			
	def on_submit(self, update_realization=True):
		super().on_submit(update_realization=False)
		if not self.material:
			self.update_rkb_realization()
		else:
			self.create_ste_issue()

	def before_save(self):
		for row in self.hasil_kerja:
			row.amount = (row.hasil or 0) * (row.rate or 0)
			if row.premi:
				row.amount += row.premi
			
	def create_ste_issue(self):
		ste = frappe.new_doc("Stock Entry")
		ste.stock_entry_type = "Material Used"
		ste.set_purpose_for_stock_entry()

		for d in self.material:
			ste.append("items", {
				"s_warehouse": d.warehouse,
				"item_code": d.item,
				"qty": d.qty,
			})
		
		ste.submit()

		self.stock_entry = ste.name
		for index, item in enumerate(ste.items):
			self.material[index].update({
				"stock_entry_detail": item.name,
				"rate": item.basic_rate,
			})

		self.set_material_rate(get_valuation_rate=False)

	def set_material_rate(self, get_valuation_rate=True):
		if get_valuation_rate:
			for d in self.material:
				d.rate = frappe.get_value("Stock Entry Detail", d.stock_entry_detail, "basic_rate")
				
		self.calculate_item_table_values()
		self.calculate_grand_total()

		self.db_update_all()

		self.update_rkb_realization()

	def on_cancel(self):
		self.delete_ste()

		super().on_cancel()

	def delete_payment_log(self):
		filters={"voucher_type": self.doctype, "voucher_no": self.name}
		for emp_log in frappe.get_all("Employee Payment Log", 
			filters=filters, pluck="name"
		):
			frappe.delete_doc("Employee Payment Log", emp_log)

	def delete_ste(self):
		if not self.stock_entry:
			return
			
		ste = frappe.get_doc("Stock Entry", self.stock_entry)
		if ste.docstatus == 1:
			ste.cancel()

		self.db_set("stock_entry", "")

		ste.delete()