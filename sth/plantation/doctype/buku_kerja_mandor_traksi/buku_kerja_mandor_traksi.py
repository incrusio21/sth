# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import get_datetime, flt
from frappe.query_builder.functions import Count

from sth.controllers.buku_kerja_mandor import BukuKerjaMandorController

class BukuKerjaMandorTraksi(BukuKerjaMandorController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		self.plantation_setting_def.extend([
			["salary_component", "bkm_traksi_component"],
			["premi_salary_component", "premi_sc"],
		])
		
		# self.max_qty_fieldname = {
        #     "hasil_kerja": "volume_basis"
        # }
		
		self.fieldname_total.extend(["premi_amount"])

		self.payment_log_updater.extend([
			{
				"target_amount": "premi_amount",
				"target_salary_component": "premi_salary_component",
                "component_type": "Premi",
				"removed_if_zero": True
			}
		])
	
	def validate(self):
		self.set_posting_datetime()
		super().validate()

		self.set_employee_premi()

	def set_posting_datetime(self):
		self.posting_datetime = f"{self.posting_date} {self.posting_time}"
	
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
			bkm_obj = frappe.get_doc(doctype="Buku Kerja Mandor Premi", employee=self.employee, voucher_type=self.doctype, posting_date=self.posting_date)
			bkm_obj.flags.ignore_permissions = 1
			bkm_obj.insert()
		except frappe.UniqueValidationError:
			frappe.db.rollback(save_point=bkm_mandor_creation_savepoint)  # preserve transaction in postgres
			bkm_obj = frappe.get_last_doc("Buku Kerja Mandor Premi", {
				"employee": self.employee, 
				"doctype": self.doctype, 
				"posting_date": self.posting_date
			})
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
		# if self.have_premi and item.qty >= self.min_basis_premi:
		# 	item.premi_amount = self.rupiah_premi

	def update_value_after_amount(self, item, precision):
		# Hitung total + premi
		item.sub_total = flt(item.amount + item.premi_amount, precision)
		
	@frappe.whitelist()
	def get_details_kendaraan(self):
		detail_kendaraan = frappe.get_cached_doc("Alat Berat Dan Kendaraan", self.kendaraan)

		hasil_kerja = self.hasil_kerja[0] if self.get("hasil_kerja") else self.append("hasil_kerja", {})
		hasil_kerja.update({
			"employee": detail_kendaraan.operator,
			**get_details_employee(detail_kendaraan.operator)
		})

		
	
	def set_traksi_premi(self):
		if self.is_heavy_equipment:
			premi_alat_berat = sorted(get_overtime_settings("roundings"), key=lambda x: x.end_time, reverse=True)

			selisih_kmhm = self.kmhm_akhir - self.kmhm_awal
			premi_value = 0
			
			for premi in premi_alat_berat:
				# hentikan jika selisih sudah lebih kecil sama dengan 0
				if selisih_kmhm <= 0:
					break
				
				# tentukan
				jumlah = premi.end_time if premi.end_time else selisih_kmhm
				premi_value += flt(premi.amount * jumlah)
				selisih_kmhm -= jumlah
		else:
			pass


@frappe.whitelist()
def get_details_employee(employee):
	hk_details = {}

	employee = frappe.get_cached_doc("Employee", detail_kendaraan.operator).as_dict()
	hasil_kerja = self.hasil_kerja[0] if self.get("hasil_kerja") else self.append("hasil_kerja", {})
	
	hasil_kerja.update({
		"holiday_list": employee.holiday_list,
		"employment_type": employee.employment_type,
		"is_holiday": frappe.db.exists("Holiday", {"parent": d.holiday_list, "holiday_date": self.posting_date}),
		"total_hari": frappe.get_value("Employment Type", employee.employment_type, "hari_ump"),
	})

	return hk_details