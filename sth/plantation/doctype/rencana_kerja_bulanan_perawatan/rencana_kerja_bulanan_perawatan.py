# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

# import frappe
from frappe.utils import flt
from sth.controllers.rencana_kerja_controller import RencanaKerjaController

class RencanaKerjaBulananPerawatan(RencanaKerjaController):
	
	def calculate_item_table_values(self):
		for df in self._get_table_fields():
			self.calculate_item_values(df.options, df.fieldname, ["budget_tambahan"])

		self.jumlah_tenaga_kerja = flt(self.qty / self.qty_basis) if self.qty_basis else 0
		self.amount = flt(self.jumlah_tenaga_kerja * self.upah_per_basis) + flt(self.premi)
