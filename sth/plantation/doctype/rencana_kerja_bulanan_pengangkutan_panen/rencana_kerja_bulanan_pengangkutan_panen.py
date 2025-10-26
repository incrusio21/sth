# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt

from sth.controllers.rencana_kerja_controller import RencanaKerjaController, get_tonase

class RencanaKerjaBulananPengangkutanPanen(RencanaKerjaController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

	def validate(self):
		self.get_tonase()
		self.validate_jarak_pks()
		super().validate()

	def validate_jarak_pks(self):
		if not self.jarak_pks:
			frappe.throw("Please fill Jarak Ke PKS First")
			
	def get_tonase(self):
		self.tonase = get_tonase(self.rencana_kerja_bulanan, {"blok": self.blok})

	def update_rate_or_qty_value(self, item, precision):
		# set on child class if needed
		if item.parentfield == "kendaraan":
			item.trip = flt(self.tonase / item.kap_kg, 0)

			item.qty = flt(item.trip * self.jarak_pks * 2, precision)

	def update_value_after_amount(self, item, precision):
		if item.parentfield == "kendaraan":
			item.rate_tbs = flt(item.amount / self.tonase, precision)