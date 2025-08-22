# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

# import frappe
from sth.controllers.budget_controller import BudgetController

class BudgetBiayaUmumTahunan(BudgetController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.duplicate_param.extend([
			"kategori_kegiatan"
		])
