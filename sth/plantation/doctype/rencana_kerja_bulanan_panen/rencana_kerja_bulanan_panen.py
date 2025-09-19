# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt 
from sth.controllers.rencana_kerja_controller import RencanaKerjaController

class RencanaKerjaBulananPanen(RencanaKerjaController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.realization_doctype = "Buku Kerja Mandor Panen"

	def validate(self):
		super().validate()
		self.check_rkb_pengangkutan()

	def calculate_item_table_values(self):
		super().calculate_item_table_values()
		
		self.jumlah_janjang = flt(self.jumlah_pokok * self.akp)
		self.tonase = flt(self.jumlah_janjang * self.bjr)
		self.total_upah = flt(self.tonase * self.upah_per_basis)
		self.pemanen_amount = flt(self.total_upah) + flt(self.premi)

	def check_rkb_pengangkutan(self):
		rkb_angkut = frappe.db.exists("Rencana Kerja Bulanan Pengangkutan Panen", 
			{
				"rencana_kerja_bulanan": self.rencana_kerja_bulanan,
				"blok": self.blok,
				"docstatus": 1
			}
		)

		if rkb_angkut:
			frappe.throw("Blok {} with {} already contains the Rencana Kerja Bulanan Pengangkutan Panen".format(self.blok, self.rencana_kerja_bulanan))
