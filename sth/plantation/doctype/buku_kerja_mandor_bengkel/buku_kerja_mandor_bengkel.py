# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from hrms.hr.doctype.attendance.attendance import DuplicateAttendanceError

class BukuKerjaMandorBengkel(Document):
	def on_submit(self):
		self.make_attendance()
		self.update_kendaraan_field(self.kmhm_akhir)
		self.make_attendance()
  
	def on_cancel(self):
		self.update_kendaraan_field(self.kmhm_awal)

	def update_kendaraan_field(self, km_value):
		if not self.kd_kndr:
			return

		frappe.db.set_value("Alat Berat Dan Kendaraan", self.kd_kndr, "kmhm_akhir", km_value)

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