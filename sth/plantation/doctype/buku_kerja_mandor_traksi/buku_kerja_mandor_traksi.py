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
		
		self.kegiatan_fetch_fieldname = []
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
		self.validate_selisih_kmhm()
		# set data emloyee
		self.set_details_diffrence(self.kmhm_awal, self.jns_alt)
		get_details_employee(self.hasil_kerja, self.posting_date)
		get_details_kegiatan(self.hasil_kerja, self.company)
		
		super().validate()

	def set_posting_datetime(self):
		self.posting_datetime = f"{self.posting_date} {self.posting_time}"
	
	def validate_selisih_kmhm(self):
		self.kmhm_awal = frappe.get_value("Alat Berat Dan Kendaraan", self.kendaraan, "kmhm_akhir")
		selisih = self.kmhm_akhir - self.kmhm_awal
		if selisih <= 0:
			frappe.throw("KM/HM Akhir cannot less than KM/HM Awal")

		self.selisih_kmhm = selisih

	def on_submit(self):
		super().on_submit()
		self.update_kendaraan_field()
		self.create_or_update_mandor_premi()

	def on_cancel(self):
		super().on_cancel()
		self.update_kendaraan_field(cancel=1)
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
			if frappe.message_log:
				frappe.message_log.pop()
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
		# if future_bkm := frappe.get_value(
		# 	"Buku Kerja Mandor Traksi", 
		# 	{"kendaraan": self.kendaraan, "docstatus": 1, "posting_datetime": [">", get_datetime(self.posting_datetime)]}, 
		# 	"name",
		# 	order_by="posting_datetime"
		# ):
		# 	status = "Submitted" if not cancel else "Canceled"
		# 	frappe.throw(f"Document cannot be {status} because Document {future_bkm} with a future date and time already exists.")
		
		# # memastikan kmhm sesuai dengan yang ada pata keendaraan
		# if not cancel and alat_kendaraan.kmhm_akhir != self.kmhm_awal:
		# 	frappe.throw(f"Initial KM/HM on the document does not match the final KM/HM on {self.kendaraan}. Save to get newest Data")
		
		# ubah nilai pada kendaraan sesuai dengan document
		new_value = self.kmhm_awal if cancel else self.kmhm_akhir
		frappe.db.set_value("Alat Berat Dan Kendaraan", self.kendaraan, "kmhm_akhir", new_value)
	
	def update_rate_or_qty_value(self, item, precision):
		item.rate = item.rupiah_basis
		# set rate pegawai jika bukan dump truck
		if self.tipe_master_kendaraan not in ("Dump Truck"):
			item.rate = flt(item.base/item.total_hari, precision)

		if not self.get("manual_hk"):
			item.hari_kerja = min(flt(item.qty / (item.volume_basis or 1)), 1)
		
		item.premi_amount = 0
		if self.tipe_master_kendaraan in ("Alat Berat"):
			item.premi_amount = flt(self.premi_heavy_equipment)
		else:
			self.set_premi_non_heavy_equipment(item, precision)

	def set_premi_non_heavy_equipment(self, item, precision):
		fields =  "holiday" if item.is_holiday else "workday"
		premi = flt(self.ump_bulanan / item.total_hari) \
			if item.get(f"ump_as_{fields}") else \
			item.get(fields)
			
		item.premi_amount = flt(premi * item.qty, precision)

	def update_value_after_amount(self, item, precision):
		# Hitung total + premi
		item.sub_total = flt(item.amount + item.premi_amount, precision)
		
	@frappe.whitelist()
	def get_details_kendaraan(self):
		if not self.kendaraan:
			return
		
		detail_kendaraan = frappe.get_cached_doc("Alat Berat Dan Kendaraan", self.kendaraan)

		if not self.get("hasil_kerja"):
			self.append("hasil_kerja", {})
		
		get_details_employee(self.hasil_kerja, self.posting_date, detail_kendaraan.operator)
		self.set_details_diffrence(detail_kendaraan.kmhm_akhir, detail_kendaraan.jns_alt)

	@frappe.whitelist()
	def set_details_diffrence(self, kmhm_awal=None, jenis_alat=None):
		if not self.kendaraan:
			return
		
		if not kmhm_awal:
			kmhm_awal = frappe.db.get_value("Alat Berat Dan Kendaraan", self.kendaraan, "kmhm_akhir")
		
		jenis_alat = frappe.get_cached_doc("Jenis Alat", self.jenis_alat).as_dict() \
			if self.tipe_master_kendaraan in ("Alat Berat") else {}

		kmhm_akhir = kmhm_awal
		for hk in self.hasil_kerja:
			if not hk.kmhm_ahkir or hk.kmhm_ahkir < kmhm_akhir:
				hk.kmhm_ahkir = kmhm_akhir

			hk.premi_heavy_equipment = 0
			if jenis_alat.get("premi"):
				selisih_kmhm = floor((hk.kmhm_ahkir - kmhm_akhir)/60)
				for premi in jenis_alat.premi:
					# hentikan jika selisih sudah lebih kecil sama dengan 0
					if selisih_kmhm <= premi.start_time:
						break
					
					jumlah = premi.end_time if premi.end_time and selisih_kmhm > premi.end_time else selisih_kmhm
					print(jumlah)
					hk.premi_heavy_equipment += flt(premi.amount * jumlah)
					selisih_kmhm -= jumlah

			kmhm_akhir = hk.kmhm_ahkir

		self.kmhm_akhir = kmhm_akhir

@frappe.whitelist()
def get_details_employee(childrens, posting_date, new_employee=None):
	if isinstance(childrens, str):
		childrens = json.loads(childrens)
	
	emloyee_dict = {}
	for ch in childrens:
		# set employee baru jika ada
		if new_employee:
			ch.set("employee", new_employee)

		# simpan dalam variabel dict agar data dengan employee sama tidak perlu melakukan query lagi
		if not emloyee_dict.get(ch.get("employee")):
			employee = frappe.get_cached_doc("Employee", ch.get("employee")).as_dict()

			emloyee_dict.setdefault(ch.get("employee"), {
				"holiday_list": employee.holiday_list,
				"employment_type": employee.employment_type,
				"is_holiday": 1 if frappe.db.exists("Holiday", {"parent": employee.holiday_list, "holiday_date": posting_date}) else 0,
				"total_hari": frappe.get_value("Employment Type", employee.employment_type, "hari_ump"),
				"base": frappe.get_value("Salary Structure Assignment", {
					"employee": employee.name, "company": employee.company, "from_date": ["<=", posting_date]
				}, "base", order_by="from_date desc"),
			})

		ch.update(emloyee_dict.get(ch.get("employee")))

	return childrens

@frappe.whitelist()
def get_details_kegiatan(childrens, company):
	if isinstance(childrens, str):
		childrens = json.loads(childrens)
	
	# load detail kegiatan
	def _get_kegiatan_upah():
		kegiatan = frappe.qb.DocType("Kegiatan Company")

		result = (
			frappe.qb.from_(kegiatan)
			.select(
				kegiatan.parent, 
				kegiatan.account, kegiatan.volume_basis,
				kegiatan.rupiah_basis, kegiatan.workday, kegiatan.holiday,
				kegiatan.workday_base, kegiatan.holiday_base
			)
			.where(
				(kegiatan.company == company) &
				(kegiatan.parent.isin([d.get("kegiatan") for d in childrens]))
			)
		).run()

		return {row[0] : frappe._dict(zip([
			"kegiatan_account", "volume_basis", "rupiah_basis",
			"workday", "holiday", 
			"ump_as_workday", "ump_as_holiday"
		], row[1:], strict=False)) for row in result}
	
	kegiatan_details = _get_kegiatan_upah()

	for ch in childrens:
		# update table dengan details kegiatan
		if kegiatan := kegiatan_details.get(ch.get("kegiatan")):
			ch.update(kegiatan)

	return childrens