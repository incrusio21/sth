import frappe
from frappe.utils import getdate
from hrms.hr.doctype.attendance.attendance import Attendance
from hrms.hr.utils import (
	get_holiday_dates_for_employee,
	get_holidays_for_employee,
	validate_active_employee,
)

from sth.custom.api import USER_API

# Field yang tidak ikut ditimpa waktu kiriman API memperbarui Attendance yang
# sudah ada: identitas dokumennya sendiri dan jejak siapa/kapan membuatnya.
# docstatus sengaja ikut dilindungi — kiriman mesin selalu berisi 1, dan itu
# tidak boleh mengubah status dokumen yang sudah ada.
FIELD_TIDAK_DITIMPA = {
	"name",
	"owner",
	"creation",
	"modified",
	"modified_by",
	"docstatus",
	"idx",
	"doctype",
	"parent",
	"parentfield",
	"parenttype",
	"amended_from",
}


def cari_attendance_kembar(doc):
	"""Attendance lain untuk employee dan tanggal yang sama, atau None.

	Cerminan `Attendance.get_duplicate_attendance_record()` milik hrms — yang
	kalau ketemu melempar DuplicateAttendanceError. Ditulis ulang karena versi
	hrms membandingkan dengan `self.name`, padahal sebelum insert nama dokumennya
	belum ada.

	Aturan shift-nya diikuti: kalau kiriman punya shift, yang dianggap kembar
	cuma baris tanpa shift atau baris ber-shift sama.
	"""
	if not doc.employee or not doc.attendance_date:
		return None

	kandidat = frappe.get_all(
		"Attendance",
		filters={
			"employee": doc.employee,
			"attendance_date": getdate(doc.attendance_date),
			"docstatus": ("<", 2),
		},
		fields=["name", "shift"],
		order_by="creation",
	)

	for row in kandidat:
		if row.name == doc.name:
			continue

		if not doc.shift or not row.shift or row.shift == doc.shift:
			return row.name

	return None


def timpa_field_dari_api(doc, kiriman):
	"""Salin isi kiriman API ke Attendance yang sudah ada.

	Field kosong dilewat: dokumen kiriman berisi juga field yang tidak dikirim
	pemanggilnya, dan nilai kosong itu tidak boleh menghapus isi yang lama.
	Akibatnya field memang tidak bisa dikosongkan lewat API — untuk integrasi ini
	kirim ulang selalu berarti menambah keterangan, bukan menghapusnya.
	"""
	for field in kiriman.meta.get_valid_columns():
		if field in FIELD_TIDAK_DITIMPA:
			continue

		nilai = kiriman.get(field)
		if nilai in (None, ""):
			continue

		doc.set(field, nilai)


def perbarui_attendance(nama, kiriman):
	"""Perbarui Attendance yang sudah ada dengan isi kiriman API."""
	doc = frappe.get_doc("Attendance", nama)
	timpa_field_dari_api(doc, kiriman)

	if doc.docstatus == 0:
		# masih draft: lewat submit biasa, validate-nya ikut jalan seperti
		# kiriman API yang lain (after_insert -> approve_api juga menyubmit)
		doc.submit()
		return doc

	# sudah disubmit: diperbarui di tempat supaya nomor dokumennya tidak berubah
	# tiap mesin mengirim ulang. Premi, is_holiday, status_code, dan Employee
	# Payment Log dihitung ulang lewat jalur yang memang disediakan untuk itu.
	doc.db_update()
	doc.run_method("repair_employee_payment_log")

	return doc


class Attendance(Attendance):

	def insert(self, *args, **kwargs):
		"""Kiriman API untuk tanggal yang sudah ada jadi update, bukan insert.

		Mesin absensi mengirim ulang tanggal yang sama — jam pulang menyusul jam
		masuk, atau kiriman diulang karena jaringan — dan insert kedua kena
		DuplicateAttendanceError dari hrms. Yang dibutuhkan integrasinya memang
		upsert: satu baris per employee per tanggal, isinya yang terbaru.

		Sengaja dibatasi ke user API. Dari UI dan data import, dua Attendance di
		tanggal yang sama tetap ditolak seperti biasa — di sana duplikat berarti
		salah input, bukan kiriman ulang.
		"""
		if frappe.session.user != USER_API:
			return super().insert(*args, **kwargs)

		kembar = cari_attendance_kembar(self)
		if kembar:
			return perbarui_attendance(kembar, self)

		# Kiriman mesin berisi docstatus 1, dan dokumen yang masuk langsung
		# sebagai tersubmit tidak pernah menjalankan on_submit: _action baru
		# bernilai "submit" kalau baris sebelumnya draft di database, dan itu
		# mustahil saat insert. Premi jadi tidak pernah tercatat sebagai Employee
		# Payment Log. Karena itu dimasukkan sebagai draft dulu, biar
		# after_insert -> approve_api yang menyubmit lewat jalur normal.
		self.docstatus = 0

		return super().insert(*args, **kwargs)

	def validate(self):
		from erpnext.controllers.status_updater import validate_status

		if self.status not in ["Present", "Absent", "On Leave", "Half Day", "Work From Home", "7th Day Off"]:
			leave_type = self.status
			self.status = "On Leave"
			self.leave_type = leave_type

		validate_status(self.status, ["Present", "Absent", "On Leave", "Half Day", "Work From Home", "7th Day Off"])
		# validate_active_employee(self.employee)
		self.validate_attendance_date()
		if self.designation not in ["NS29","NS30","NS08"]:
			self.validate_duplicate_record()

		self.validate_overlapping_shift_attendance()
		# self.validate_employee_status()
		self.check_leave_record()
