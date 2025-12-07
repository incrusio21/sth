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
		
		self.max_qty_fieldname = {
            "hasil_kerja": "volume_basis"
        }
		
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

	def set_employee_premi(self):
		for d in self.hasil_kerja:
			# check apakah merupakan hari libur pegawai
			self.is_holiday = frappe.db.exists("Holiday", {"parent": d.holiday_list, "holiday_date": self.posting_date})
			if self.is_holiday:
				pass				

	def on_submit(self):
		super().on_submit()
		self.update_kendaraan_field()
		self.create_or_update_mandor_premi()

	def create_or_update_mandor_premi(self):
		bkm_mandor_creation_savepoint = "create_bkm_mandor"
		try:
			frappe.db.savepoint(bkm_mandor_creation_savepoint)
			bkm_obj = frappe.get_doc(doctype="Buku Kerja Mandor Premi", employee=self.employee, posting_date=self.posting_date)
			bkm_obj.flags.ignore_permissions = 1
			bkm_obj.insert()
		except frappe.UniqueValidationError:
			frappe.db.rollback(save_point=bkm_mandor_creation_savepoint)  # preserve transaction in postgres
			bkm_obj = frappe.get_last_doc("Buku Kerja Mandor Premi", {"employee": self.employee, "posting_date": self.posting_date})
			bkm_obj.save()

		# jika ada grand total maka update payment log
		if bkm_obj.grand_total:
			bkm_obj.create_or_update_payment_log()

		self.db_set("buku_kerja_mandor_premi", bkm_obj.name)

	def on_cancel(self):
		super().on_cancel()
		self.update_kendaraan_field()
		self.check_and_remove_mandor_premi()
	
	def check_and_remove_mandor_premi(self):
		Traksi = frappe.qb.DocType("Buku Kerja Mandor Traksi")

		bkm_premi = self.buku_kerja_mandor_premi

		# Group by kategori tertentu
		traksi_count = (
			frappe.qb.from_(Traksi)
			.select(
				Count(Traksi.name)
			)
			.where(
				(Traksi.buku_kerja_mandor_premi == bkm_premi) & 
				(Traksi.name != self.name)
			)
		).run()[0][0] or 0

		self.db_set("buku_kerja_mandor_premi", None)
		if not traksi_count:
			frappe.delete_doc("Buku Kerja Mandor Premi", bkm_premi)

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
		item.premi_amount = 0

		if not self.get("manual_hk"):
			item.hari_kerja = min(flt(item.qty / (self.volume_basis or 1)), 1)
		
		if self.have_premi and item.qty >= self.min_basis_premi:
			item.premi_amount = self.rupiah_premi

	def update_value_after_amount(self, item, precision):
		# Hitung total + premi
		item.sub_total = flt(item.amount + item.premi_amount, precision)
		
	@frappe.whitelist()
	def get_details_kendaraan(self):
		detail_kendaraan = frappe.get_cached_doc("Alat Berat Dan Kendaraan", self.kendaraan)

		hasil_kerja = self.hasil_kerja[0] if self.get("hasil_kerja") else self.append("hasil_kerja", {})
		hasil_kerja.update({
			"employee": detail_kendaraan.operator
		})
			
		