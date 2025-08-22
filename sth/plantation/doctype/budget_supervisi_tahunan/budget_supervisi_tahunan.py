# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt
from sth.controllers.budget_controller import BudgetController

class BudgetSupervisiTahunan(BudgetController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.skip_table_amount = ["distribusi"]
		self.duplicate_param.extend([
			"divisi"
		])

	def validate(self):
		super().validate()
		self.set_distribusi_rate()

	def set_distribusi_rate(self):
		precision = frappe.get_precision("Detail Budget Distribusi", "rate")
		rate_distribusi = flt(self.grand_total / self.jml_hk, precision)
		for item in self.distribusi:
			item.rate = rate_distribusi

		# hitung ulang nilai distribusi
		self.calculate_item_values("Detail Budget Distribusi", "distribusi")

