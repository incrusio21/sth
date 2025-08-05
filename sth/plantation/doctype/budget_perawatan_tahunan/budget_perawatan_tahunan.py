# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

# import frappe

from frappe.utils import flt
from sth.controllers.budget_controller import BudgetController


class BudgetPerawatanTahunan(BudgetController):
	def validate(self):
		super().validate()
		self.set_uom_upah_perawatan()
		self.set_volume_total()

	def set_uom_upah_perawatan(self):
		for d in self.upah_perawatan:
			d.uom = self.uom

	def set_volume_total(self):
		table_field = self.get("upah_bibitan" if self.is_bibitan else "upah_perawatan")
		self.volume_total = self.mean_rotasi = self.ha_per_tahun = 0.0
		volume_total = mean_rotasi = 0.0
		
		for item in table_field:
			volume_total += item.qty
			mean_rotasi += item.rotasi

		if table_field:
			self.volume_total = flt(volume_total)
			self.mean_rotasi = flt(mean_rotasi/len(table_field))
			self.ha_per_tahun = flt(self.grand_total / self.volume_total)