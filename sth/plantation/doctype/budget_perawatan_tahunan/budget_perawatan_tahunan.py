# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

# import frappe

from frappe.utils import flt
from sth.controllers.budget_controller import BudgetController


class BudgetPerawatanTahunan(BudgetController):
	def validate(self):
		super().validate()
		self.set_uom_upah_perawatan()
		self.set_ha_per_tahun()

	def set_uom_upah_perawatan(self):
		for d in self.upah_perawatan:
			d.uom = self.uom

	def set_ha_per_tahun(self):
		table_field = "upah_bibitan" if self.is_bibitan else "upah_perawatan"
		self.ha_per_tahun = flt(self.grand_total / self.get(f"{table_field}_qty"))
