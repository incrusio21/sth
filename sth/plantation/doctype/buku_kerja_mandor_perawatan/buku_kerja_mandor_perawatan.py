# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe

from frappe.utils import flt
from sth.controllers.buku_kerja_mandor import BukuKerjaMandorController

class BukuKerjaMandorPerawatan(BukuKerjaMandorController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		self.plantation_setting_def.extend([
			["salary_component", "bkm_perawatan_component"],
			["premi_salary_component", "premi_sc"],
		])
		
		self.fieldname_total.extend(["premi_amount"])

		self.kegiatan_fetch_fieldname.extend(["min_basis_premi", "rupiah_premi"])

		self.payment_log_updater.extend([
			{
				"target_amount": "premi_amount",
				"target_salary_component": "premi_salary_component",
                "component_type": "Premi",
				"removed_if_zero": True
			}
		])

		self._mandor_dict = []

	def validate(self):
		self.validate_hasil_kerja_harian()
		super().validate()
		
	def validate_hasil_kerja_harian(self):
		if self.get("is_bibitan"):
			return
		
		if self.uom == "HA" and self.hasil_kerja_qty > self.luas_blok:
			frappe.throw("Hasil Kerja exceeds Luas Blok")

	def update_rate_or_qty_value(self, item, precision):
		if item.parentfield != "hasil_kerja":
			return
		
		item.rate = item.get("rate") or self.rupiah_basis
		item.premi_amount = 0

		if not self.manual_hk:
			item.hari_kerja = min(flt(item.qty / (self.volume_basis or 1)), 1)
		
		if self.have_premi and item.qty >= self.min_basis_premi:
			item.premi_amount = self.rupiah_premi

	def update_value_after_amount(self, item, precision):
		if item.parentfield != "hasil_kerja":
			return
		
		# Hitung total brondolan
		item.sub_total = flt(item.amount + item.premi_amount, precision)
		
	def on_submit(self, update_realization=True):

		super().on_submit(update_realization=False)
		if not self.material:
			pass
			# self.update_rkb_realization()
		else:
			self.create_ste_issue()
			
	def create_ste_issue(self):
		ste = frappe.new_doc("Stock Entry")
		ste.stock_entry_type = "Material Used"
		ste.posting_date = self.posting_date
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

		# self.update_rkb_realization()

	def on_cancel(self):
		self.delete_ste()

		super().on_cancel()

	def delete_ste(self):
		if not self.stock_entry:
			return
			
		ste = frappe.get_doc("Stock Entry", self.stock_entry)
		if ste.docstatus == 1:
			ste.cancel()

		self.db_set("stock_entry", "")

		ste.delete()