# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

# import frappe
from frappe.utils import flt
from sth.controllers.rencana_kerja_controller import RencanaKerjaController

class RencanaKerjaBulananUmum(RencanaKerjaController):
	def update_rate_or_qty_value(self, item, precision):
		if not item.rate:
			# set on child class if needed
			item.rate = self.ump_harian

	def update_value_after_amount(self, item, precision):
		# set on child class if needed
		item.amount = flt(item.amount + (item.get("premi") or 0) + (item.get("budget_tambahan") or 0) , precision)