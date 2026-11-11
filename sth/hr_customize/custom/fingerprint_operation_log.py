# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

"""Attendance otomatis dari Fingerprint Operation Log (app iclock).

Mesin mengirim OPLOG dalam bentuk JSON di field `data`, satu baris per kejadian:

    [["OPLOG 3", "31740331059300", "2026-11-09 16:27:11", "53", "0", "0", "0"]]

Kolom kedua adalah operator, yang untuk OPLOG 3 berisi `finger_id` Employee. Satu
log bisa membawa banyak baris lintas hari kalau mesin baru tersambung lagi.

Aturannya per employee per tanggal:
- baru satu waktu  -> Attendance draft, in_time terisi
- dua waktu berbeda -> out_time terisi (waktu paling akhir), Attendance disubmit
- waktu berikutnya  -> in_time/out_time diperlebar kalau lebih awal/akhir

Attendance yang sudah ada dari input manual, API, atau BKM tidak disentuh — tidak
dibuat baru dan tidak diubah. Yang dibuat di sini ditandai lewat trans_no.
"""

import json

import frappe
from frappe.utils import get_datetime, getdate
from hrms.hr.doctype.attendance.attendance import DuplicateAttendanceError

from sth.overrides.attendance import cari_attendance_kembar

# Kejadian yang dihitung sebagai absen. Kode lain (masuk menu, daftar sidik jari,
# dll) juga membawa operator, tapi itu bukan tanda kehadiran.
OPLOG_ABSEN = "OPLOG 3"

# Penanda Attendance buatan modul ini, disimpan di trans_no. Kiriman API memakai
# trans_no sendiri (CIN...), jadi tidak bertabrakan.
PREFIX_TRANS_NO = "FINGER/"


def enqueue_attendance(doc, method=None):
	"""after_insert: diproses di background.

	Log masuk lewat request mesin sebagai Guest, dan satu log bisa ratusan baris.
	Request mesin tidak boleh lambat atau gagal karena Attendance-nya bermasalah —
	mesin akan mengirim ulang terus.
	"""
	frappe.enqueue(
		"sth.hr_customize.custom.fingerprint_operation_log.proses_log",
		log_name=doc.name,
		queue="short",
		enqueue_after_commit=True,
	)


def proses_log(log_name):
	# Guest tidak boleh membuat Attendance maupun Employee Payment Log yang ikut
	# dibuat saat submit
	frappe.set_user("Administrator")

	log = frappe.db.get_value(
		"Fingerprint Operation Log", log_name, ["data", "serial_number"], as_dict=True
	)
	if not log:
		return

	for (finger_id, tanggal), waktu in kelompokkan_absen(log.data).items():
		try:
			frappe.db.savepoint("fingerprint_attendance")
			catat_absen(finger_id, tanggal, waktu, log.serial_number)
		except Exception:
			frappe.db.rollback(save_point="fingerprint_attendance")
			frappe.log_error(
				title="Attendance dari fingerprint gagal",
				message="Log {0}, finger_id {1}, tanggal {2}\n\n{3}".format(
					log_name, finger_id, tanggal, frappe.get_traceback()
				),
				reference_doctype="Fingerprint Operation Log",
				reference_name=log_name,
			)


def kelompokkan_absen(data):
	"""{(finger_id, tanggal): [datetime, ...]} dari isi field data."""
	try:
		baris = json.loads(data or "[]")
	except ValueError:
		return {}

	hasil = {}
	for row in baris:
		if not isinstance(row, list) or len(row) < 3 or row[0] != OPLOG_ABSEN:
			continue

		finger_id = (row[1] or "").strip()
		if not finger_id or finger_id == "0":
			continue

		try:
			waktu = get_datetime(row[2])
		except Exception:
			continue

		hasil.setdefault((finger_id, waktu.date()), []).append(waktu)

	return hasil


def catat_absen(finger_id, tanggal, waktu, serial_number):
	employee = cari_employee(finger_id)
	if not employee:
		return

	kunci = frappe._dict(employee=employee.name, attendance_date=tanggal, shift=None, name=None)
	nama = cari_attendance_kembar(kunci)
	if not nama:
		try:
			return buat_attendance(employee, tanggal, waktu, serial_number)
		except DuplicateAttendanceError:
			if frappe.message_log:
				frappe.message_log.pop()

			# keduluan job lain untuk employee dan tanggal yang sama
			nama = cari_attendance_kembar(kunci)
			if not nama:
				raise

	perbarui_attendance(nama, waktu)


def cari_employee(finger_id):
	# old_finger_id: mesin yang belum didaftarkan ulang masih mengirim ID lama.
	# Aman karena ID baru dijamin tidak bertabrakan dengan ID lama mana pun.
	for field in ("finger_id", "old_finger_id"):
		employees = frappe.get_all(
			"Employee",
			filters={field: finger_id, "status": "Active"},
			fields=["name", "company"],
		)
		if employees:
			break

	# finger_id diambil dari 14 digit pertama no_ktp, jadi bisa kembar. Lebih
	# aman tidak mencatat daripada mencatat ke orang yang salah.
	if len(employees) > 1:
		frappe.log_error(
			title="Finger ID dipakai lebih dari satu employee",
			message="finger_id {0}: {1}".format(finger_id, ", ".join(e.name for e in employees)),
		)
		return None

	return employees[0] if employees else None


def buat_attendance(employee, tanggal, waktu, serial_number):
	masuk, pulang = min(waktu), max(waktu)

	doc = frappe.get_doc({
		"doctype": "Attendance",
		"employee": employee.name,
		"company": employee.company,
		"attendance_date": tanggal,
		"status": "Present",
		"in_time": masuk,
		"out_time": pulang if pulang != masuk else None,
		"trans_no": PREFIX_TRANS_NO + (serial_number or ""),
	})
	doc.flags.ignore_permissions = 1
	doc.insert()

	if doc.out_time:
		doc.submit()

	return doc.name


def perbarui_attendance(nama, waktu):
	doc = frappe.get_doc("Attendance", nama)

	# manual, API, BKM: dibiarkan apa adanya
	if not (doc.trans_no or "").startswith(PREFIX_TRANS_NO):
		return

	semua = list(waktu) + [get_datetime(t) for t in (doc.in_time, doc.out_time) if t]
	masuk, pulang = min(semua), max(semua)
	if pulang == masuk:
		pulang = None

	if get_datetime(doc.in_time) == masuk and (doc.out_time and get_datetime(doc.out_time)) == pulang:
		return

	if doc.docstatus == 0:
		doc.in_time = masuk
		doc.out_time = pulang
		doc.flags.ignore_permissions = 1
		if pulang:
			doc.submit()
		else:
			doc.save()
		return

	# sudah disubmit: cuma jamnya yang berubah, status dan premi tetap
	doc.db_set({"in_time": masuk, "out_time": pulang})


def proses_ulang(dari=None, sampai=None):
	"""Proses ulang log yang sudah masuk, misalnya sebelum hook ini terpasang.

	Aman diulang: Attendance yang sudah ada hanya diperlebar jamnya.

	    bench --site <site> execute sth.hr_customize.custom.fingerprint_operation_log.proses_ulang --kwargs "{'dari': '2026-11-01'}"
	"""
	filters = {}
	if dari and sampai:
		filters["creation"] = ("between", [getdate(dari), getdate(sampai)])
	elif dari:
		filters["creation"] = (">=", getdate(dari))
	elif sampai:
		filters["creation"] = ("<=", getdate(sampai))

	user = frappe.session.user
	try:
		for i, nama in enumerate(frappe.get_all(
			"Fingerprint Operation Log", filters=filters, order_by="creation", pluck="name"
		), 1):
			proses_log(nama)
			if i % 200 == 0:
				frappe.db.commit()
	finally:
		frappe.db.commit()
		frappe.set_user(user)
