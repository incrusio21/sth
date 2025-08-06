# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

# import frappe
from sth.controllers.budget_controller import BudgetController

class BudgetPanenTahunan(BudgetController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.skip_table_amount = ["tonase"]
