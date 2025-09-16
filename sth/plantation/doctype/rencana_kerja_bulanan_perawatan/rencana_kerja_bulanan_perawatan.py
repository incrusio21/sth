# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt
from frappe.query_builder.functions import Sum

from sth.controllers.rencana_kerja_controller import RencanaKerjaController

class RencanaKerjaBulananPerawatan(RencanaKerjaController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.realization_doctype = "Buku Kerja Mandor Perawatan"

	def calculate_item_table_values(self):
		super().calculate_item_table_values()
		
		self.jumlah_tenaga_kerja = flt(self.qty / self.qty_basis) if self.qty_basis else 0
		self.tenaga_kerja_amount = flt(self.jumlah_tenaga_kerja * self.upah_per_basis) + flt(self.premi)

	def calculate_used_and_realized(self):
		super().calculate_used_and_realized()

		rkh_m = frappe.qb.DocType("Detail RKH Material")
		rkh = frappe.qb.DocType("Rencana Kerja Harian")
		
		material_used = frappe._dict(
			(
				frappe.qb.from_(rkh_m)
				.inner_join(rkh)
            	.on(rkh.name == rkh_m.parent)
				.select(
					rkh_m.prevdoc_detail, Sum(rkh_m.amount)
				)
				.where(
					(rkh.docstatus == 1) &
					(rkh.voucher_type == self.doctype) &
                	(rkh.voucher_no == self.name)
				)
				.groupby(rkh_m.prevdoc_detail)
			).run()
		)
		
		bkm_m = frappe.qb.DocType("Detail BKM Material")
		bkm = frappe.qb.DocType(self.realization_doctype)
		
		material_real = frappe._dict(
			(
				frappe.qb.from_(bkm_m)
				.inner_join(bkm)
            	.on(bkm.name == bkm_m.parent)
				.select(
					bkm_m.prevdoc_detail, Sum(bkm_m.amount)
				)
				.where(
					(bkm.docstatus == 1) &
					(bkm.voucher_type == self.doctype) &
                	(bkm.voucher_no == self.name)
				)
				.groupby(bkm_m.prevdoc_detail)
			).run()
		)

		for d in self.material:
			used_total = material_used.get(d.name) or 0.0
			if used_total > d.amount:
				frappe.throw("Used Total exceeds Amount of Item {}.".format(d.item))

			real_total = material_real.get(d.name) or 0.0
			if real_total > d.amount:
				frappe.throw("Realization Total exceeds Amount of Item {}.".format(d.item))
		
			d.used_total = used_total
			d.realized_total = real_total
			d.db_update()
