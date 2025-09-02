# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

# import frappe
from frappe.utils import flt 
from sth.controllers.rencana_kerja_controller import RencanaKerjaController

class RencanaKerjaBulananPanen(RencanaKerjaController):
	def calculate_item_table_values(self):
		super().calculate_item_table_values()
		
		self.jumlah_janjang = flt(self.jumlah_pokok * self.akp)
		self.tonase = flt(self.jumlah_janjang * self.bjr)
		self.total_upah = flt(self.tonase / self.upah_per_basis) if self.upah_per_basis else 0
		self.pemanen_amount = flt(self.total_upah) + flt(self.premi)
