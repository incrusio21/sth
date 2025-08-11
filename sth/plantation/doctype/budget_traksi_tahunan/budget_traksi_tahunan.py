# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

# import frappe
from frappe.utils import flt
from sth.controllers.budget_controller import BudgetController


class BudgetTraksiTahunan(BudgetController):
	def validate(self):
		super().validate()
		self.set_rp_per_km_hm()

	def set_rp_per_km_hm(self):
		self.rp_kmhm = flt(self.grand_total / self.total_km_hm, self.precision("rp_kmhm"))

