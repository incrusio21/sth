# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt
from frappe.query_builder.functions import Sum

from sth.controllers.rencana_kerja_controller import RencanaKerjaController

class RencanaKerjaBulananPerawatan(RencanaKerjaController):
	def calculate_item_table_values(self):
		super().calculate_item_table_values()
		
		self.jumlah_tenaga_kerja = flt(self.qty / self.qty_basis) if self.qty_basis else 0
		self.tenaga_kerja_amount = flt(self.jumlah_tenaga_kerja * self.upah_per_basis) + flt(self.premi)

	def update_used_total(self):
		super().update_used_total()

		rkh_m = frappe.qb.DocType("Detial RKH Material")
		rkh = frappe.qb.DocType("Rencana Kerja Harian")
		
		material_used = frappe._dict(
			(
				frappe.qb.from_(rkh)
				.select(
					rkh_m.prevdoc_detail, Sum(rkh.kegiatan_amount)
				)
				.where(
					(rkh.docstatus == 1) &
					(rkh.kode_kegiatan == self.kode_kegiatan) & 
					(rkh.divisi == self.divisi) &
					(rkh.blok == self.blok) &
					(rkh.tanggal_transaksi.between(self.from_date, self.to_date))
				)
				.group_by(rkh_m.prevdoc_detail)
			).run()
		)

		for d in self.material:
			d.db_set("used_amount", material_used.get(d.name) or 0.0) 

