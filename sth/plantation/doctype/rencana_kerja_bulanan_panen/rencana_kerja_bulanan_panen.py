# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt 
from sth.controllers.rencana_kerja_controller import RencanaKerjaController

class RencanaKerjaBulananPanen(RencanaKerjaController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.realization_doctype = "Buku Kerja Mandor Panen"
		self.kegiatan_fetch_fieldname = ["volume_basis", "rupiah_basis"]

	def validate(self):
		super().validate()
		self.check_pengangkutan_and_supervisi()

	def calculate_item_table_values(self):
		super().calculate_item_table_values()
		
		self.jumlah_janjang = flt(self.jumlah_pokok * self.akp/100)
		self.tonase = flt(self.jumlah_janjang * self.bjr)
		if not self.jumlah_tenaga_kerja and self.volume_basis:
			self.jumlah_tenaga_kerja = flt(self.tonase / self.volume_basis)
			
		self.total_upah = flt(self.tonase * self.rupiah_basis)
		self.pemanen_amount = flt(self.total_upah) + flt(self.premi)

	def before_calculate_grand_total(self):
		self.supervisi_amount = flt(self.upah_supervisi) + flt(self.premi_supervisi)

	def check_pengangkutan_and_supervisi(self):
		rkb_angkut = frappe.db.exists("Rencana Kerja Bulanan Pengangkutan Panen", 
			{
				"rencana_kerja_bulanan": self.rencana_kerja_bulanan,
				"blok": self.blok,
				"docstatus": 1
			}
		)

		if rkb_angkut:
			frappe.throw("Blok {} with {} already contains the Rencana Kerja Bulanan Pengangkutan Panen".format(self.blok, self.rencana_kerja_bulanan))

		rkb_supervisi = frappe.db.exists("Rencana Kerja Bulanan Supervisi Panen", 
			{
				"rencana_kerja_bulanan": self.rencana_kerja_bulanan,
				"divisi": self.divisi,
				"docstatus": 1
			}
		)

		if rkb_supervisi:
			frappe.throw("Divisi {} with {} already contains the Rencana Kerja Bulanan Supervisi Panen".format(self.divisi, self.rencana_kerja_bulanan))

	def update_upah_supervisi(self, doc=None):
		
		self.upah_supervisi = self.premi_supervisi = 0
		if doc and doc.docstatus == 1:
			self.upah_supervisi = flt(doc.upah_supervisi * self.tonase / doc.total_tonase)
			self.premi_supervisi = flt(doc.premi_supervisi * self.tonase / doc.total_tonase)

		self.calculate()