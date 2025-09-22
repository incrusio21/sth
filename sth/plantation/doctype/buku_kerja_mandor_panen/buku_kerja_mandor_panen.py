# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt
from frappe.query_builder.functions import Coalesce, Sum

from sth.controllers.buku_kerja_mandor import BukuKerjaMandorController


class BukuKerjaMandorPanen(BukuKerjaMandorController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fieldname_total.extend([
			"hari_kerja", "qty", "qty_brondolan"
		])

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

	def after_calculate_item_values(self, table_fieldname, options, total):
		if table_fieldname == "hasil_kerja":
			self.hari_kerja_total = flt(total["hari_kerja"])

	def update_kontanan_used(self):
		ppk = frappe.qb.DocType("Pengajuan Panen Kontanan")

		kontanan = (
			frappe.qb.from_(ppk)
			.select(
				ppk.name
            )
			.where(
                (ppk.docstatus == 1) &
                (ppk.bkm_panen == self.name)
			)
		).run()

		if kontanan and len(kontanan) > 1:
			frappe.throw("BKM Panen already used")

		self.db_set("is_used", 1 if kontanan else 0)

	def calculate_transfered_weight(self):
		spb = frappe.qb.DocType("SPB Timbangan Pabrik")

		self.transfered_hasil_kerja, self.transfered_brondolan, self.weight_total = (
			frappe.qb.from_(spb)
			.select(
				Coalesce(Sum(spb.qty), 0), 
				Coalesce(Sum(spb.brondolan_qty), 0),
				Coalesce(Sum(spb.netto_weight), 0)
            )
			.where(
                (spb.docstatus == 1) &
                (spb.bkm_panen == self.name)
			)
		).run()[0]

		if self.transfered_hasil_kerja > self.hasil_kerja_qty:
			frappe.throw("Transfered Janjang exceeds limit.")

		if self.transfered_brondolan > self.hasil_kerja_qty:
			frappe.throw("Transfered Brondolan exceeds limit.")

		self.bjr = 0.0
		if self.weight_total and self.transfered_hasil_kerja:
			self.bjr = flt((self.weight_total - self.transfered_brondolan) / self.transfered_hasil_kerja, self.precision("bjr"))

		self.db_update()
