# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from hrms.hr.doctype.attendance.attendance import DuplicateAttendanceError

class BukuKerjaMandorBengkel(Document):
	def validate(self):
		self.update_kendaraan_field()

	def on_submit(self):
		self.make_attendance()
		self.make_attendance()

	def on_cancel(self):
		self.update_kendaraan_field(cancel=1)

	def on_trash(self):
		self.update_kendaraan_field(cancel=1)

	def update_kendaraan_field(self, cancel=0):
		if not self.kd_kndr:
			return

		from sth.plantation.doctype.alat_berat_dan_kendaraan.alat_berat_dan_kendaraan import sync_kmhm_akhir

		if cancel:
			# doc dibatalkan/dihapus, jangan ikut dihitung sebagai kandidat
			sync_kmhm_akhir(self.kd_kndr, exclude=self.name)
		else:
			sync_kmhm_akhir(
				self.kd_kndr,
				candidate_kmhm_akhir=self.kmhm_akhir,
				candidate_sort_dt=f"{self.posting_date} 23:59:59",
				exclude=self.name,
			)

	def make_attendance(self):
		for emp in self.hasil_kerja:
			attendance_detail = {
				"employee": emp.employee, "company": self.company, "attendance_date": self.posting_date
			}

			add_att = "add_attendance"
			try:
				frappe.db.savepoint(add_att)
				attendance = frappe.get_doc({
					"doctype": "Attendance",
					"status": emp.status,
					**attendance_detail
				})
				attendance.flags.ignore_permissions = 1
				attendance.submit()
			except DuplicateAttendanceError:
				if frappe.message_log:
					frappe.message_log.pop()
					
				frappe.db.rollback(save_point=add_att)  # preserve transaction in postgres
				
@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_employee_traksi_query(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""
			SELECT e.name, e.employee_name
			FROM `tabEmployee` e
			JOIN `tabDesignation` d ON d.name = e.designation
			WHERE d.is_jabatan_traksi = 1
			AND (e.name LIKE %(txt)s OR e.employee_name LIKE %(txt)s)
			LIMIT %(start)s, %(page_len)s
	""", {
			"txt": f"%{txt}%",
			"start": start,
			"page_len": page_len
	})