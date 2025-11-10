# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt, get_link_to_form
from frappe.query_builder.functions import Coalesce, Sum

from sth.controllers.buku_kerja_mandor import BukuKerjaMandorController


class BukuKerjaMandorPanen(BukuKerjaMandorController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.plantation_setting_def.extend([
			["salary_component", "bkm_panen_component"],
			["denda_salary_component", "denda_sc"],
			["brondolan_salary_component", "brondolan_sc"],
			["kontanan_salary_component", "premi_kontanan_component"],
		])

		self.fieldname_total.extend([
			"jumlah_janjang", "qty_brondolan", "brondolan_amount", "denda", "kontanan_amount"
		])

		self.kegiatan_fetch_fieldname.extend(["upah_brondolan", "premi_kontanan_basis"])

		self.payment_log_updater.extend([
			{
				"target_link": "kontanan_epl",
				"target_amount": "kontanan_amount",
				"target_salary_component": "kontanan_salary_component",
				"removed_if_zero": True
			},
			{
				"target_link": "denda_epl",
				"target_amount": "denda",
				"target_salary_component": "denda_salary_component",
				"removed_if_zero": True
			},
			{
				"target_link": "brondolan_epl",
				"target_amount": "brondolan_amount",
				"target_salary_component": "brondolan_salary_component",
				"removed_if_zero": True
			}
		])

	def validate(self):
		self.reset_automated_data()

		super().validate()

	def reset_automated_data(self):
		self.transfered_janjang = self.transfered_brondolan = \
		self.netto_weight = self.weight_total = self.bjr = 0

	def set_payroll_date(self):
		if not self.is_kontanan:
			super().set_payroll_date()
		else:
			self.payroll_date, self.against_salary_component = frappe.db.get_value("Pengajuan Panen Kontanan", {
				"bkm_panen": self.name, "docstatus": 1
			}, ["posting_date", "against_kontanan_component"]) or ["", ""]

	def on_submit(self):
		self.set_status()

		super().on_submit()

	def set_status(self, update_payment_log=False):
		if frappe.db.exists("Rekap Timbangan Panen", {"buku_kerja_mandor_panen": self.name, "docstatus": 1}):
			self.db_set("status", "Approved")
		else:
			self.db_set("status", "Pending")

		if update_payment_log:
			self.calculate()
			self.create_or_update_payment_log()

	def set_salary_component(self):
		hr_panen = frappe.db.get_value("Plantation Settings", None, ["denda_sc", "brondolan_sc"], as_dict=1)

		self.denda_salary_component = hr_panen.denda_sc
		self.brondolan_sc = hr_panen.brondolan_sc
		
	def update_rate_or_qty_value(self, item, precision):
		if item.parentfield != "hasil_kerja":
			return
		
		item.bjr = self.bjr
		item.qty = (item.bjr * item.jumlah_janjang)
		item.rate = flt(item.get("rate") or self.rupiah_basis)
		item.brondolan = flt(self.upah_brondolan)

		item.hari_kerja = min(flt(item.qty / self.volume_basis), 1)

	def update_value_after_amount(self, item, precision):
		# Hitung total brondolan
		item.brondolan_amount = flt(item.brondolan * flt(item.qty_brondolan), precision)
		item.kontanan_amount = flt(item.qty * flt(self.premi_kontanan_basis), precision) if self.is_kontanan else 0

		# Perhitungan denda
		factors = [ 
			"buah_tidak_dipanen", "buah_mentah_disimpan", "buah_mentah_ditinggal",
			"brondolan_tinggal", "pelepah_tidak_disusun","tangkai_panjang",
			"buah_tidak_disusun", "pelepah_sengkleh"
		]

		# Hitung total denda dengan menjumlahkan rate * nilai item
		item.denda = sum(flt(item.get(field)) * flt(self.get(f"{field}_rate")) for field in factors)

		item.sub_total = flt(item.amount + item.brondolan_amount + item.kontanan, precision)

	def after_calculate_grand_total(self):
		self.grand_total -= self.hasil_kerja_denda 

	def update_kontanan_used(self):
		if not self.is_rekap:
			frappe.throw("Please Rekap BKM Panen {} first".format(
				get_link_to_form(self.doctype, self.name)
			))

		self.set_payroll_date()
		self.db_update()
		
		self.set_status(update_payment_log=True)

	def calculate_transfered_weight(self):
		spb = frappe.qb.DocType("SPB Timbangan Pabrik")

		transfered_janjang = (
			frappe.qb.from_(spb)
			.select(
				Coalesce(Sum(spb.qty), 0)
            )
			.where(
                (spb.docstatus == 1) &
                (spb.bkm_panen == self.name)
			)
		).run()[0][0]

		transfered_restan = (
			frappe.qb.from_(spb)
			.select(
				Coalesce(Sum(spb.qty_restan), 0), 
            )
			.where(
                (spb.docstatus == 1) &
                (spb.bkm_panen_restan == self.name)
			)
		).run()[0][0]

		self.transfered_janjang = flt(transfered_janjang + transfered_restan, self.precision("transfered_janjang"))

		if self.transfered_janjang > self.hasil_kerja_jumlah_janjang:
			frappe.throw("Transfered Janjang exceeds limit.")

		self.db_update()

	def set_data_rekap_weight(self):
		if self.against_salary_component:
			frappe.throw("BKM Panen {} already used in Pembayaran Kontanan".format(
				get_link_to_form(self.doctype, self.name)
			))

		spb = frappe.qb.DocType("Rekap Timbangan Panen")

		rekap_timbangan = (
			frappe.qb.from_(spb)
			.select(
				spb.bjr, 
				spb.total_weight
            )
			.where(
                (spb.docstatus == 1) &
                (spb.buku_kerja_mandor_panen == self.name)
			)
		).run()

		if len(rekap_timbangan) > 1:
			frappe.throw("Only one Rekap timbangan Panen is allowed per document")

		self.is_rekap, values = (1, rekap_timbangan[0]) if rekap_timbangan else (0, (0, 0))
		self.bjr, self.weight_total = values

		self.set_status(update_payment_log=True)
		self.db_update()
