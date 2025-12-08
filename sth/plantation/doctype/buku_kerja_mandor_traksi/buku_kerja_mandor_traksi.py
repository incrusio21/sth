# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import json
import frappe
from frappe.utils import floor, flt, get_datetime

from sth.controllers.buku_kerja_mandor import BukuKerjaMandorController

class BukuKerjaMandorTraksi(BukuKerjaMandorController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		self.plantation_setting_def.extend([
			["salary_component", "bkm_traksi_component"],
			["premi_salary_component", "premi_sc"],
		])
		
		self.fieldname_total.extend(["premi_amount"])

		self.payment_log_updater.extend([
			{
				"target_amount": "premi_amount",
				"target_salary_component": "premi_salary_component",
                "component_type": "Premi",
				"removed_if_zero": True
			}
		])

		self.kegiatan_fetch_fieldname.extend([
			"workday as premi_workday", "holiday as premi_holiday", 
			"workday_base as ump_as_workday", "holiday_base as ump_as_holiday"
		])
	
	def validate(self):
		self.set_posting_datetime()
		self.validate_selisih_kmhm()
		self.set_premi_heavy_equipment()
		super().validate()

		self.validate_details_employee()

	def set_posting_datetime(self):
		self.posting_datetime = f"{self.posting_date} {self.posting_time}"
	
	def validate_selisih_kmhm(self):
		selisih = self.kmhm_akhir - self.kmhm_awal
		if selisih <= 0:
			frappe.throw("KM/HM Akhir cannot less than KM/HM Awal")

		self.selisih_kmhm = selisih

	def set_premi_heavy_equipment(self):
		self.premi_heavy_equipment = 0
		if not self.is_heavy_equipment:
			return
		
		jenis_alat = frappe.get_cached_doc("Jenis Alat", self.jenis_alat).as_dict()

		selisih_kmhm = floor(self.selisih_kmhm/60)
		premi_value = 0		
		for premi in jenis_alat.premi:
			# hentikan jika selisih sudah lebih kecil sama dengan 0
			if selisih_kmhm <= 0:
				break
			
			jumlah = premi.end_time if premi.end_time else selisih_kmhm
			premi_value += flt(premi.amount * jumlah)
			selisih_kmhm -= jumlah

		self.premi_heavy_equipment = premi_value

	def validate_details_employee(self):
		get_details_employee(self.hasil_kerja, self.posting_date)

	def on_submit(self):
		super().on_submit()
		self.update_kendaraan_field()
		self.create_or_update_mandor_premi()

	def on_cancel(self):
		super().on_cancel()
		self.update_kendaraan_field()
		self.create_or_update_mandor_premi()
	
	def create_or_update_mandor_premi(self):
		bkm_mandor_creation_savepoint = "create_bkm_mandor"
		try:
			frappe.db.savepoint(bkm_mandor_creation_savepoint)
			bkm_obj = frappe.get_doc(doctype="Buku Kerja Mandor Premi", employee=self.mandor, voucher_type=self.doctype, posting_date=self.posting_date)
			bkm_obj.flags.ignore_permissions = 1
			bkm_obj.flags.transaction_employee = 1
			bkm_obj.insert()
		except frappe.UniqueValidationError:
			frappe.db.rollback(save_point=bkm_mandor_creation_savepoint)  # preserve transaction in postgres
			bkm_obj = frappe.get_last_doc("Buku Kerja Mandor Premi", {
				"employee": self.mandor, 
				"posting_date": self.posting_date,
				"voucher_type": self.doctype
			})
			bkm_obj.flags.transaction_employee = 1
			bkm_obj.save()

	def update_kendaraan_field(self, cancel=0):
		if not self.kendaraan:
			return

		# cek apakah terdapat future pemakaian kendaraan
		if future_bkm := frappe.get_value(
			"Buku Kerja Mandor Traksi", 
			{"kendaraan": self.kendaraan, "docstatus": 1, "posting_datetime": [">", get_datetime(self.posting_datetime)]}, 
			"name",
			order_by="posting_datetime"
		):
			status = "Submitted" if not cancel else "Canceled"
			frappe.throw(f"Document cannot be {status} because Document {future_bkm} with a future date and time already exists.")
		
		alat_kendaraan = frappe.get_doc("Alat Berat Dan Kendaraan", self.kendaraan, for_update=1)
		# memastikan kmhm sesuai dengan yang ada pata keendaraan
		if not cancel and alat_kendaraan.kmhm_akhir != self.kmhm_awal:
			frappe.throw(f"Initial KM/HM on the document does not match the final KM/HM on {self.kendaraan}")
		
		# ubah nilai pada kendaraan sesuai dengan document
		new_value = self.kmhm_awal if cancel else self.kmhm_akhir
		frappe.db.set_value("Alat Berat Dan Kendaraan", self.kendaraan, "kmhm_akhir", new_value)
	
	def update_rate_or_qty_value(self, item, precision):
		item.rate = item.get("rate") or self.rupiah_basis
		# set rate pegawai jika bukan dump truck
		if self.tipe_master_kendaraan not in ("Dump Truck"):
			item.rate = flt(item.base/item.total_hari, precision)

		if not self.get("manual_hk"):
			item.hari_kerja = min(flt(item.qty / (self.volume_basis or 1)), 1)
		
		item.premi_amount = 0
		if self.is_heavy_equipment:
			item.premi_amount = flt(self.premi_heavy_equipment)
		else:
			self.set_premi_non_heavy_equipment(item, precision)

	def set_premi_non_heavy_equipment(self, item, precision):
		fields =  "holiday" if item.is_holiday else "workday"
		premi = flt(self.ump_bulanan / item.total_hari) \
			if self.get(f"ump_as_{fields}") else \
			self.get(f"premi_{fields}")
			
		item.premi_amount = flt(premi * item.qty, precision)

	def update_value_after_amount(self, item, precision):
		# Hitung total + premi
		item.sub_total = flt(item.amount + item.premi_amount, precision)
		
	@frappe.whitelist()
	def get_details_kendaraan(self):
		if not self.kendaraan:
			return
		
		detail_kendaraan = frappe.get_cached_doc("Alat Berat Dan Kendaraan", self.kendaraan)

		hasil_kerja = self.hasil_kerja[0] if self.get("hasil_kerja") else self.append("hasil_kerja", {})
		hasil_kerja.update(
			get_details_employee([{"employee": detail_kendaraan.operator}], self.posting_date)[0]
		)
	
@frappe.whitelist()
def get_details_employee(childrens, posting_date):
	if isinstance(childrens, str):
		childrens = json.loads(childrens)
	
	for ch in childrens:
		employee = frappe.get_cached_doc("Employee", ch.get("employee")).as_dict()

		ch.update({
			"holiday_list": employee.holiday_list,
			"employment_type": employee.employment_type,
			"is_holiday": 1 if frappe.db.exists("Holiday", {"parent": employee.holiday_list, "holiday_date": posting_date}) else 0,
			"total_hari": frappe.get_value("Employment Type", employee.employment_type, "hari_ump"),
			"base": frappe.get_value("Salary Structure Assignment", {
				"employee": employee.name, "company": employee.company, "from_date": ["<=", posting_date]
			}, "base", order_by="from_date desc"),
		})

	return childrens