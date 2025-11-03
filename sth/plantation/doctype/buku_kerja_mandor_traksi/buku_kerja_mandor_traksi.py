# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from hrms.hr.doctype.attendance.attendance import DuplicateAttendanceError

class BukuKerjaMandorTraksi(Document):

	@frappe.whitelist()
	def get_employee_traksi(self):
		return frappe.db.sql("""
			SELECT e.name, d.designation_name
			FROM `tabEmployee` e
			JOIN `tabDesignation` d ON d.name = e.designation
			WHERE d.is_jabatan_traksi = 1
		""", as_dict=True)

	@frappe.whitelist()
	def get_employee_supervisi(self):
		return frappe.db.sql("""
			SELECT e.name, d.designation_name
			FROM `tabEmployee` e
			JOIN `tabDesignation` d ON d.name = e.designation
			WHERE d.custom_supervisi = 'Traksi'
		""", as_dict=True)

	@frappe.whitelist() 
	def get_volume_basis_kegiatan(self, kegiatan, company):
		volume_basis = frappe.db.sql("""
			SELECT 
			k.name,
			kc.account,
			kc.volume_basis
			FROM `tabKegiatan` as k
			JOIN `tabKegiatan Company` as kc ON kc.parent = k.name
			WHERE k.name = %s AND kc.company = %s
			LIMIT 1;
		""", (kegiatan, company), as_dict=True)
		return volume_basis[0]['volume_basis']

	@frappe.whitelist() 
	def get_min_basis_premi_and_rupiah_premi_kegiatan(self, kegiatan, company):
		volume_basis = frappe.db.sql("""
			SELECT 
			k.name,
			kc.account,
			kc.min_basis_premi,
			kc.rupiah_premi
			FROM `tabKegiatan` as k
			JOIN `tabKegiatan Company` as kc ON kc.parent = k.name
			WHERE k.name = %s AND kc.company = %s
			LIMIT 1;
		""", (kegiatan, company), as_dict=True)
		return {
			"min_basis_premi": volume_basis[0]['min_basis_premi'],
			"rupiah_premi": volume_basis[0]['rupiah_premi'],
		}

	def before_save(self):
		if self.jk == "Dump Truck":
			volume_basis = self.get_volume_basis_kegiatan(self.kegiatan, self.company)
			self.hari_kerja = self.hari_kerja = 1 if (self.hk / volume_basis) > 1 else round(self.hk / volume_basis, 2)

			self.pekerjaan_subtotal = (self.hk * self.rupiah_basis) + self.rupiah_premi
		else:
			self.operator_subtotal = self.uph + self.premi
			self.hari_kerja = 1

	def on_submit(self):
		self.make_attendance()
		self.make_employee_payment_log()
		self.update_kendaraan_field(self.kmhm_akhir)

	def on_cancel(self):
		self.delete_payment_log()
		self.update_kendaraan_field(self.kmhm_awal)

	def update_kendaraan_field(self, km_value):
		if not self.kdr:
			return

		frappe.db.set_value("Alat Berat Dan Kendaraan", self.kdr, "kmhm_akhir", km_value)

	def make_employee_payment_log(self):
		plantation_settings = frappe.get_single("Plantation Settings")

		account = frappe.db.sql("""
			SELECT 
				k.name,
				kc.account
			FROM `tabKegiatan` AS k
			JOIN `tabKegiatan Company` AS kc ON kc.parent = k.name
			WHERE k.name = %s AND kc.company = %s
		""", (self.kegiatan, self.company), as_dict=True)

		upah_amount = self.subtotal_upah if self.jk == "Dump Truck" else self.uph
		premi_amount = self.rupiah_premi if self.jk == "Dump Truck" else self.premi

		upah_log = frappe.new_doc("Employee Payment Log")
		upah_log.update({
			"employee": self.nk,
			"hari_kerja": self.hari_kerja,
			"company": self.company,
			"posting_date": self.tgl_trk,
			"payroll_date": self.tgl_trk,
			"status": "Approved",
			"is_paid": 0,
			"amount": upah_amount,
			"salary_component": plantation_settings.bkm_traksi_component,
			"account": account[0]['account']
		})
		upah_log.insert(ignore_permissions=True)
		upah_log.submit()
		self.db_set("employee_payment_log_upah", upah_log.name)
		
		if premi_amount and premi_amount != 0:
			premi_log = frappe.new_doc("Employee Payment Log")
			premi_log.update({
				"employee": self.nk,
				"hari_kerja": self.hari_kerja,
				"company": self.company,
				"posting_date": self.tgl_trk,
				"payroll_date": self.tgl_trk,
				"status": "Approved",
				"is_paid": 0,
				"amount": premi_amount,
				"salary_component": plantation_settings.premi_sc_traksi,
				"account": account[0]['account']
			})
			premi_log.insert(ignore_permissions=True)
			premi_log.submit()
			self.db_set("employee_payment_log_premi", premi_log.name)

	def delete_payment_log(self):
		if self.employee_payment_log_upah:
			log_name = self.employee_payment_log_upah
			self.db_set("employee_payment_log_upah", None)
			frappe.delete_doc("Employee Payment Log", log_name, force=1)

		if self.employee_payment_log_premi:
			log_name = self.employee_payment_log_premi
			self.db_set("employee_payment_log_premi", None)
			frappe.delete_doc("Employee Payment Log", log_name, force=1)

	def make_attendance(self):
		savepoint = "add_attendance"
		try:
			frappe.db.savepoint(savepoint)

			attendance = frappe.new_doc("Attendance")
			attendance.update({
				"employee": self.nk,
				"employee_name": self.nk,
				"status": self.status,
				"company": self.company,
				"attendance_date": self.tgl_trk
			})
			attendance.flags.ignore_permissions = True
			attendance.submit()

		except DuplicateAttendanceError:
			if frappe.message_log:
				frappe.message_log.pop()
			frappe.db.rollback(save_point=savepoint)
