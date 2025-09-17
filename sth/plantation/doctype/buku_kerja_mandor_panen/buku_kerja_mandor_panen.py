# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt

from sth.controllers.buku_kerja_mandor import BukuKerjaMandorController


class BukuKerjaMandorPanen(BukuKerjaMandorController):
	def validate(self):
		super().validate()
		self.calculate_brondolan_qty()

	def calculate_brondolan_qty(self):
		brondolan_qty = 0.0
		for d in self.hasil_kerja:
			brondolan_qty += d.qty_brondolan or 0

		self.brondolan_qty = brondolan_qty
		
	def update_rate_or_qty_value(self, item, precision):
		if item.parentfield != "hasil_kerja":
			return
		
		item.rate = item.get("rate") or self.rp_per_basis
		item.brondolan = self.upah_brondolan

		# perhitungan denda
		buah_tidak_dipanen = flt(self.buah_tidak_dipanen_rate * flt(item.buah_tidak_dipanen))
		buah_mentah_disimpan = flt(self.buah_mentah_disimpan_rate * flt(item.buah_mentah_disimpan))
		buah_mentah_ditinggal = flt(self.buah_mentah_ditinggal_rate * flt(item.buah_mentah_ditinggal))
		brondolan_tinggal = flt(self.brondolan_tinggal_rate * flt(item.brondolan_tinggal))
		pelepah_tidak_disusun = flt(self.pelepah_tidak_disusun_rate * flt(item.pelepah_tidak_disusun))
		tangkai_panjang = flt(self.tangkai_panjang_rate * flt(item.tangkai_panjang))
		buah_tidak_disusun = flt(self.buah_tidak_disusun_rate * flt(item.buah_tidak_disusun))
		pelepah_sengkleh = flt(self.pelepah_sengkleh_rate * flt(item.pelepah_sengkleh))

		item.brondolan = flt(item.brondolan * flt(item.qty_brondolan))
		item.denda = flt(buah_tidak_dipanen + buah_mentah_disimpan + buah_mentah_ditinggal + brondolan_tinggal +
					pelepah_tidak_disusun + tangkai_panjang + buah_tidak_disusun + pelepah_sengkleh)
	
	def update_value_after_amount(self, item, precision):
		item.amount += item.brondolan_amount - flt(item.denda)
