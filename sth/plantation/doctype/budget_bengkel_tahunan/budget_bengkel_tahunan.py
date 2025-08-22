# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

# import frappe
from frappe.utils import flt
from sth.controllers.budget_controller import BudgetController

class BudgetBengkelTahunan(BudgetController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.skip_table_amount = ["distribusi"]
		self.duplicate_param.extend([
			"kode_bengkel"
		])

	def validate(self):
		super().validate()
		self.set_rp_per_jam()

	def set_rp_per_jam(self):
		self.rp_kmhm = flt(self.grand_total / self.jam_per_tahun, self.precision("rp_kmhm"))
