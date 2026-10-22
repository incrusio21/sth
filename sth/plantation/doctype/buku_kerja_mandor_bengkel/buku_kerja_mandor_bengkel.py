# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt

class BukuKerjaMandorBengkel(Document):
	def validate(self):
		self.validate_kmhm()
		self.update_kendaraan_field()

	def validate_kmhm(self):
		# KM/HM akhir yang dibiarkan kosong tersimpan 0 dan lewat sync_kmhm_akhir
		# ikut mengenolkan KM/HM master kendaraan. Kendaraan di bengkel tidak
		# berjalan, jadi kosong berarti sama dengan awal.
		if not flt(self.kmhm_akhir):
			self.kmhm_akhir = flt(self.kmhm_awal)

		if flt(self.kmhm_akhir) < flt(self.kmhm_awal):
			frappe.throw(f"KM/HM Akhir ({self.kmhm_akhir}) tidak boleh lebih kecil dari KM/HM Awal ({self.kmhm_awal})")

	def on_submit(self):
		self.make_attendance()

	def on_cancel(self):
		from sth.overrides.attendance import hapus_catatan_bkm

		self.update_kendaraan_field(cancel=1)
		hapus_catatan_bkm(self)

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

	def make_attendance(self, buat_baru=True):
		from sth.overrides.attendance import catat_attendance_bkm

		# lihat make_attendance di BukuKerjaMandorController
		tanpa_attendance = []

		# Bengkel tidak punya kegiatan, cukup nomor BKM-nya yang dicatat
		for emp in self.hasil_kerja:
			nama = catat_attendance_bkm(self, emp.employee, emp.status, peran="Pekerja", buat_baru=buat_baru)
			if emp.employee and not nama:
				tanpa_attendance.append(emp.employee)

		return tanpa_attendance

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