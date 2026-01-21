# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PermintaanPengeluaranBarang(Document):
	def on_submit(self):
		self.db_set("status","Submitted")
	
	def update_outgoing_percentage(self):
		qty = 0
		out_qty = 0

		for row in self.items:
			qty += row.jumlah
			out_qty += row.jumlah_keluar
		
		outgoing_percent = out_qty/qty * 100

		self.db_set("outgoing",outgoing_percent)


	def update_status(self):
		self.update_outgoing_percentage()

		if self.outgoing == 100:
			self.db_set("status","Barang Telah Dikeluarkan")
		elif self.outgoing > 0:
			self.db_set("status","Sebagian di Keluarkan")
		