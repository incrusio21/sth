import frappe
from frappe.utils import getdate
from hrms.hr.doctype.attendance.attendance import Attendance, DuplicateAttendanceError
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

# Mesin absensi mengirim company sebagai singkatan, bukan nama Company-nya.
# Dipetakan di sini supaya kiriman tetap nyambung ke Link Company yang benar.
COMPANY_DARI_SINGKATAN = {
	"TML": "PT. TRIMITRA LESTARI",
}


def normalisasi_company(nilai):
	"""Ubah singkatan company kiriman API jadi nama Company yang sebenarnya."""
	if isinstance(nilai, str):
		return COMPANY_DARI_SINGKATAN.get(nilai.strip().upper(), nilai)

	return nilai


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

		if field == "company":
			nilai = normalisasi_company(nilai)

		doc.set(field, nilai)


def catat_attendance_bkm(bkm, employee, status, peran, kegiatan=None, buat_baru=True):
	"""Pastikan employee punya Attendance di tanggal BKM, lalu catat BKM-nya di sana.

	Attendance yang sudah ada — dari mesin absensi, input manual, atau BKM lain di
	hari yang sama — dipakai apa adanya, statusnya tidak diubah. BKM cuma menambah
	baris di tabel bkm_attendance, dengan status versi BKM-nya sendiri, supaya
	kelihatan kegiatan mana saja yang menyatakan employee ini masuk hari itu.

	buat_baru=False dipakai pengisian mundur: Attendance yang belum ada tidak
	dibuat, karena itu berarti menambah premi ke periode yang sudah berjalan.
	Mengembalikan nama Attendance-nya, atau None kalau tidak ada.
	"""
	if not employee:
		return

	kunci = frappe._dict(employee=employee, attendance_date=bkm.posting_date, shift=None, name=None)
	nama = cari_attendance_kembar(kunci)
	if not nama and buat_baru:
		nama = buat_attendance_bkm(bkm, employee, status, kunci)
	if not nama:
		return

	attendance = frappe.get_doc("Attendance", nama)
	for k in kegiatan or [None]:
		sudah_dicatat = any(
			r.voucher_type == bkm.doctype
			and r.voucher_no == bkm.name
			and (r.kegiatan or None) == k
			and r.peran == peran
			for r in attendance.bkm_attendance
		)
		if sudah_dicatat:
			continue

		# disisipkan langsung, bukan lewat save(): Attendance yang sudah disubmit
		# tidak perlu menjalankan validate dan menghitung ulang preminya cuma
		# karena ada BKM baru yang menunjuknya
		row = attendance.append("bkm_attendance", {
			"voucher_type": bkm.doctype,
			"voucher_no": bkm.name,
			"kegiatan": k,
			"peran": peran,
			"status": status,
		})
		row.docstatus = attendance.docstatus
		row.db_insert()

	return nama


def buat_attendance_bkm(bkm, employee, status, kunci):
	savepoint = "add_attendance"
	try:
		frappe.db.savepoint(savepoint)
		attendance = frappe.get_doc({
			"doctype": "Attendance",
			"employee": employee,
			"company": bkm.company,
			"attendance_date": bkm.posting_date,
			"status": status,
		})
		attendance.flags.ignore_permissions = 1
		attendance.submit()

		return attendance.name

	except DuplicateAttendanceError:
		if frappe.message_log:
			frappe.message_log.pop()

		frappe.db.rollback(save_point=savepoint)  # preserve transaction in postgres

		# keduluan permintaan lain yang menyisipkan di saat bersamaan
		return cari_attendance_kembar(kunci)


def hapus_catatan_bkm(bkm):
	"""Lepas catatan BKM yang dibatalkan dari Attendance yang ditunjuknya.

	Attendance-nya sendiri tidak ikut dibatalkan — perilakunya sama seperti
	sebelum ada catatan ini. Harus jalan di on_cancel, sebelum frappe mengecek
	back link: baris yang tertinggal membuat Attendance tersubmit masih menunjuk
	BKM-nya, dan pembatalan ditolak.
	"""
	frappe.db.delete("BKM Attendance", {
		"parenttype": "Attendance",
		"voucher_type": bkm.doctype,
		"voucher_no": bkm.name,
	})


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

		self.company = normalisasi_company(self.company)

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
		# Dulu Montir, Danru, dan Satpam (NS08, NS29, NS30) dikecualikan di sini,
		# dan itulah sumber Attendance dobel di tanggal yang sama. Kiriman ulang
		# mesin sudah ditangani insert() di atas, jadi tidak ada lagi alasan
		# membolehkan dua Attendance untuk satu employee di satu tanggal.
		self.validate_duplicate_record()

		self.validate_overlapping_shift_attendance()
		# self.validate_employee_status()
		self.check_leave_record()
