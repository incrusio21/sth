# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt
from frappe.query_builder.functions import Sum

from sth.controllers.rencana_kerja_controller import RencanaKerjaController

class RencanaKerjaBulananPengangkutanPanen(RencanaKerjaController):
	def validate(self):
		self.get_tonase()
		self.vliadate_jarak_pks()
		super().validate()

	def vliadate_jarak_pks(self):
		if not self.jarak_pks:
			frappe.throw("Please fill Jarak Ke PKS First")
			
	def get_tonase(self):
		self.tonase = get_tonase(self.rencana_kerja_bulanan, self.blok)

	def update_rate_or_qty_value(self, item, precision):
        # set on child class if needed
		if item.parentfield == "kendaraan":
			item.qty = flt(self.tonase / item.kap_kg * self.jarak_pks * 2, precision)

@frappe.whitelist()
def get_tonase(rkb, blok):
	rkb_panen = frappe.qb.DocType("Rencana Kerja Bulanan Panen")

	query = (
		frappe.qb.from_(rkb_panen)
		.select(
			Sum(rkb_panen.tonase)
		)
		.where(
			(rkb_panen.docstatus == 1) &
			(rkb_panen.rencana_kerja_bulanan == rkb) &
			(rkb_panen.blok == blok)
		)
	)

	return query.run()[0][0] or 0.0