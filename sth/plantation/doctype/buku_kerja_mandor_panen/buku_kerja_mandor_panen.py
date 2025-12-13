# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt, format_date, get_link_to_form
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
				"target_amount": "kontanan_amount",
				"target_salary_component": "kontanan_salary_component",
                "component_type": "Kontanan",
				"removed_if_zero": True
			},
			{
				"target_amount": "denda",
				"target_salary_component": "denda_salary_component",
                "component_type": "Denda",
				"removed_if_zero": True
			},
			{
				"target_amount": "brondolan_amount",
				"target_salary_component": "brondolan_salary_component",
                "component_type": "Brondolan",
				"removed_if_zero": True
			}
		])

		self._clear_fields = ["blok"]
		self._mandor_dict.append({"fieldname": "mandor1"})

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
		super().on_submit()
		self.create_recap_panen_by_blok()

	def create_recap_panen_by_blok(self):
		blok_dict = {}
		for hk in self.hasil_kerja:
			blok = blok_dict.setdefault(hk.blok, {
				"voucher_type": self.doctype, 
				"voucher_no": self.name,
				"company": self.company,
				"posting_date": self.posting_date,
				"jumlah_janjang": 0,
				"jumlah_brondolan": 0,
				"kontanan": self.is_kontanan
			})

			blok["jumlah_janjang"] += hk.jumlah_janjang
			blok["jumlah_brondolan"] += hk.qty_brondolan
		
		message = ""
		for b, value in blok_dict.items():
			rekap_panen = "create_rekap_panen"
			try:
				frappe.db.savepoint(rekap_panen)
				rpb = frappe.new_doc("Recap Panen by Blok")
				rpb.blok = b
				rpb.update(value)
				rpb.save()
			except frappe.UniqueValidationError:
				if frappe.message_log:
					frappe.message_log.pop()
					
				frappe.db.rollback(save_point=rekap_panen)  # preserve transaction in postgres
				message += f"<br>{b}"

		if message:
			frappe.throw(f"List Blok already used in {format_date(self.posting_date)}: {message}")

	def on_cancel(self):
		super().on_cancel()
		self.delete_recap_panen()

	def delete_recap_panen(self):
		for epl in frappe.get_all(
			"Recap Panen by Blok", 
			filters={"voucher_type": self.doctype, "voucher_no": self.name}, 
			pluck="name"
		):
			frappe.delete_doc("Recap Panen by Blok", epl, flags=frappe._dict(transaction_panen=True))
		
	def update_rate_or_qty_value(self, item, precision):
		if item.parentfield != "hasil_kerja":
			return
		
		item.qty = flt((item.bjr or 0) * item.jumlah_janjang)
		item.rate = item.get("rate") or self.rupiah_basis
		item.brondolan = flt(self.upah_brondolan)
		item.status = "Pending" if not item.bjr else "Approved"

		if not self.manual_hk:
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

		item.sub_total = flt(item.amount + item.brondolan_amount + item.kontanan_amount, precision)

	def after_calculate_grand_total(self):
		self.grand_total -= self.hasil_kerja_denda 

	def update_kontanan_used(self, cancel=0):
		self.set_payroll_date()
		self.is_rekap = not cancel
		self.db_update()
		
		self.create_or_update_payment_log()

	def update_hasil_kerja_bjr(self, block_dict=None):
		# update bjr untuk menentukan nilai upah pegawai
		update_payment_log = []
		for hk in self.hasil_kerja:
			if block_dict and not block_dict.get(hk.blok):
				continue
			
			hk.bjr = block_dict[hk.blok]
			update_payment_log.append(hk.name)

		self.calculate()
		self.db_update_all()
		
		if self.is_kontanan and self.is_rekap:
			frappe.throw(f"Document already have Pengajuan Kontanan. please cancel it first")

		self.create_or_update_payment_log(update_payment_log, "Upah")