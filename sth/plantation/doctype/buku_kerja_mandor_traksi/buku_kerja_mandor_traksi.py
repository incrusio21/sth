# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import json
import frappe
from frappe.utils import cstr, floor, flt, get_datetime
from frappe.query_builder.functions import IfNull

import erpnext
from erpnext.accounts.general_ledger import merge_similar_entries

from sth.controllers.buku_kerja_mandor import BukuKerjaMandorController

class BukuKerjaMandorTraksi(BukuKerjaMandorController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		self.plantation_setting_def.extend([
			["salary_component", "bkm_traksi_component"],
			["premi_salary_component", "premi_sc"],
		])
		
		self.kegiatan_fetch_fieldname = []
		self.skip_calculate_table = ["task"]
		self.fieldname_total.extend(["premi_amount"])

		self.payment_log_updater = [
            {
                "target_amount": "amount",
                "target_account": "kegiatan_account",
                "target_salary_component": "salary_component",
                "component_type": "Upah",
                "hari_kerja": True,
                "removed_if_zero": False,
            },
			{
				"target_amount": "premi_amount",
				"target_salary_component": "premi_salary_component",
                "component_type": "Premi",
				"removed_if_zero": True
			}
        ]

		self._clear_fields = ["blok", "divisi", "batch", "project"]
		
	def validate(self):
		self.set_posting_datetime()
		self.set_salary_account()
		
		# jika merupakan document baru. nama sudah d update sebelum data update
		if self.flags.in_insert:
			self.update_task_details_name()
		
		# set data emloyee
		self.validate_upah_kegiatan()
		self.set_details_diffrence(jenis_alat=self.jenis_alat, raise_error=True)
		get_details_employee(self.hasil_kerja, self.posting_date)
		get_details_kegiatan(self.hasil_kerja, self.company)
		
		super().validate()

	def set_posting_datetime(self):
		self.posting_datetime = f"{self.posting_date} {self.posting_time}"
	
	def set_salary_account(self):
		self.salary_account = frappe.db.get_value(
			"Salary Component Account",
			{"parent": self.salary_component, "company": self.company},
			"account",
			cache=True,
		)

	def validate_upah_kegiatan(self):
		for tk in self.task:
			tk.amount = flt(tk.hasil_kerja) * flt(tk.upah_hasil)
	
	@frappe.whitelist()
	def set_details_diffrence(self, kmhm_awal=None, jenis_alat=None, raise_error=False):
		if not self.kendaraan:
			return
		
		if not kmhm_awal:
			kmhm_awal = frappe.db.get_value("Alat Berat Dan Kendaraan", self.kendaraan, "kmhm_akhir", for_update=self.docstatus)
		
		jenis_alat = frappe.get_cached_doc("Jenis Alat", self.jenis_alat).as_dict() \
			if self.tipe_master_kendaraan in ("Alat Berat") else {}

		self.kmhm_awal = kmhm_awal

		kmhm_akhir = kmhm_awal
		for tk in self.task:
			tk.kmhm_awal = kmhm_akhir

			if not tk.kmhm_akhir or tk.kmhm_akhir < kmhm_akhir:
				tk.kmhm_akhir = kmhm_akhir

			tk.premi_heavy_equipment = 0
			if jenis_alat.get("premi"):
				selisih_kmhm = floor((tk.kmhm_akhir - kmhm_akhir)/60)
				for premi in jenis_alat.premi:
					# hentikan jika selisih sudah lebih kecil sama dengan 0
					if selisih_kmhm < premi.start_time:
						break
					
					jumlah = premi.end_time if premi.end_time and selisih_kmhm > premi.end_time else selisih_kmhm
					
					tk.premi_heavy_equipment += flt(premi.amount * jumlah)
					selisih_kmhm -= jumlah

			kmhm_akhir = tk.kmhm_akhir

		self.kmhm_akhir = kmhm_akhir
		if raise_error and (self.kmhm_akhir - self.kmhm_awal) <= 0:
			frappe.throw("KM/HM Akhir cannot less than or same with KM/HM Awal")

	def on_update(self):
		if not self.flags.in_insert:
			self.update_task_details_name(update=1)

	def update_task_details_name(self, update=0):
		# Buat mapping local name ke task name
		task_name = {tk.get("localname") or tk.name: tk.name for tk in self.task}
		for hk in self.hasil_kerja:
			# Parse kegiatan list
			old_kegiatan = [s.strip() for s in cstr(hk.kegiatan_list).replace(",", "\n").split("\n") if s.strip()]
			
			# Filter dan convert ke actual task names
			new_kegiatan = [task_name[k] for k in old_kegiatan if k in task_name]
			
			hk.kegiatan_list = "\n".join(new_kegiatan)

		if update:
			self.update_child_table("hasil_kerja")

	def on_submit(self):
		super().on_submit()
		self.make_gl_entry()
		self.update_kendaraan_field()
		self.create_or_update_mandor_premi()

	def on_cancel(self):
		super().on_cancel()
		self.make_gl_entry()
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
		if future_bkm := frappe.get_value(
			"Buku Kerja Mandor Traksi", 
			{"kendaraan": self.kendaraan, "docstatus": 1, "posting_datetime": [">", get_datetime(self.posting_datetime)]}, 
			"name",
			order_by="posting_datetime"
		):
			status = "Submitted" if not cancel else "Canceled"
			frappe.throw(f"Document cannot be {status} because Document {future_bkm} with a future date and time already exists.")
		
		# # memastikan kmhm sesuai dengan yang ada pata keendaraan
		# if not cancel and alat_kendaraan.kmhm_akhir != self.kmhm_awal:
		# 	frappe.throw(f"Initial KM/HM on the document does not match the final KM/HM on {self.kendaraan}. Save to get newest Data")
		
		# ubah nilai pada kendaraan sesuai dengan document
		new_value = self.kmhm_awal if cancel else self.kmhm_akhir
		frappe.db.set_value("Alat Berat Dan Kendaraan", self.kendaraan, "kmhm_akhir", new_value)
	
	def make_gl_entry(self, gl_entries=None):
		from erpnext.accounts.general_ledger import make_gl_entries, make_reverse_gl_entries

		if not gl_entries:
			gl_entries = self.get_gl_entries()

		if self.docstatus == 1:
			make_gl_entries(
				gl_entries,
				merge_entries=False,
			)
		elif self.docstatus == 2:
			make_reverse_gl_entries(voucher_type=self.doctype, voucher_no=self.name)
			
	def get_gl_entries(self):
		gl_entries = []
		
		self._all_expense_account = set()
		self.make_kegiatan_gl_entry(gl_entries)
		gl_entries = merge_similar_entries(gl_entries)

		if self._all_expense_account:
			self.make_salary_gl_entry(gl_entries)

		return gl_entries

	def make_kegiatan_gl_entry(self, gl_entries):
		cost_center = erpnext.get_default_cost_center(self.company)

		# daftar gl entry kegiatan yang memiliki upah
		for d in self.task:
			if not d.amount:
				continue

			gl_entries.append(
				self.get_gl_dict(
					{
						"account": d.kegiatan_account,
						"against": self.salary_account,
						"credit": d.amount,
						"credit_in_account_currency": d.amount,
						"cost_center": self.get("cost_center") or cost_center,
					},
					item=self,
				)
			)

			self._all_expense_account.add(d.kegiatan_account)

	def make_salary_gl_entry(self, gl_entries):
		cost_center = erpnext.get_default_cost_center(self.company)

		gl_entries.append(
			self.get_gl_dict(
				{
					"account": self.salary_account,
					"against": ",".join(self._all_expense_account),
					"debit": self.hasil_kerja_amount,
					"debit_in_account_currency": self.hasil_kerja_amount,
					"cost_center": cost_center		
				},
				item=self,
			)
		)

	def custom_amount_value(self, item, precision):
		# centang jika upah sudah di berikan pada transaksi sebelumny 
		if item.upah_is_zero:
			item.amount = 0
			return
		
		# Hitung amount dasar
		amount = flt((item.base or 0)/item.total_hari)
		is_basic_salary = True
		item.premi_amount = 0

		task = [s.strip() for s in cstr(item.kegiatan_list).replace(",", "\n").split("\n") if s.strip()]
		for t in self.get("task", {"name": ["in", task]}):
			kegiatan = json.loads(t.company_details).get(item.position or "Operator") or {}

			if t.upah_kegiatan:
				if is_basic_salary:
					amount = 0
					is_basic_salary = False

				print(t.amount)    

				amount += t.amount

			premi_amount = 0
			
			if self.tipe_master_kendaraan in ("Alat Berat"):
				premi_amount += flt(t.premi_heavy_equipment)
			else:
				premi_amount += flt((t.hasil_kerja or 0) * 
					self.set_premi_non_heavy_equipment(item, kegiatan), 
					precision
				)
				
			item.premi_amount += premi_amount
		
		# if not self.get("manual_hk"):
		# 	item.hari_kerja = min(flt(item.qty / (item.volume_basis or 1)), 1)

		item.amount = (item.amount or amount) if is_basic_salary else amount			

	def set_premi_non_heavy_equipment(self, item, kegiatan):
		fields =  "holiday" if item.is_holiday else "workday"
		premi = flt(self.ump_bulanan / item.total_hari) \
			if kegiatan.get(f"ump_as_{fields}") else \
			kegiatan.get(fields)
			
		return premi or 0

	def update_value_after_amount(self, item, precision):
		# Hitung total + premi
		item.sub_total = flt(item.amount + item.premi_amount, precision)
		
	@frappe.whitelist()
	def get_details_kendaraan(self):
		if not self.kendaraan or not self.get("hasil_kerja"):
			return
		
		detail_kendaraan = frappe.get_doc("Alat Berat Dan Kendaraan", self.kendaraan)
				
		get_details_employee(self.hasil_kerja, self.posting_date, detail_kendaraan.operator)
		self.set_details_diffrence(detail_kendaraan.kmhm_akhir, detail_kendaraan.jns_alt)

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
def get_details_kegiatan(childrens, company, update_upah=True):
	if isinstance(childrens, str):
		childrens = json.loads(childrens)
	
	# load detail kegiatan
	def _get_kegiatan_upah():
		kegiatan = frappe.qb.DocType("Kegiatan Company")

		result = (
			frappe.qb.from_(kegiatan)
			.select(
				kegiatan.parent, IfNull(kegiatan.position, "Operator"), 
				kegiatan.account, kegiatan.use_basic_salary, kegiatan.rupiah_basis, 
				kegiatan.volume_basis, kegiatan.workday, kegiatan.holiday,
				kegiatan.workday_base, kegiatan.holiday_base
			)
			.where(
				(kegiatan.company == company) &
				(kegiatan.parent.isin([d.get("kegiatan") for d in childrens]))
			)
		).run()

		ress = {}
		for row in result:
			k = ress.setdefault(row[0], {
				"position": {}
			})

			if row[1] == "Operator":
				k["kegiatan_account"] = row[2]
				k["use_basic_salary"] = row[3]
				k["rupiah_basis"] = row[4]

			k["position"][row[1]] = frappe._dict(zip([
				"volume_basis",
				"workday", "holiday", 
				"ump_as_workday", "ump_as_holiday"
			], row[5:], strict=False))


		return ress
	
	kegiatan_details = _get_kegiatan_upah()
	for ch in childrens:
		upah = ch.get("upah_hasil")
		kc = kegiatan_details.get(ch.get("kegiatan")) or {}

		upah_kegiatan = not kc.get("use_basic_salary", 0)
		if update_upah:
			upah = kc.get("rupiah_basis", 0) if upah_kegiatan else 0
			
		ch.update({
			"upah_hasil": upah,
			"kegiatan_account": kc.get("kegiatan_account"),
			"upah_kegiatan": upah_kegiatan,
			"amount": flt(upah) * flt(ch.get("hasil_kerja")),
			"company_details": json.dumps(kc.get("position", {}))
		})

	return childrens