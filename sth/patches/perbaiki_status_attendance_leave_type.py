import frappe

from sth.overrides.attendance import STATUS_ATTENDANCE


def execute():
	"""Perbaiki Attendance yang status-nya berisi nama Leave Type.

	Kiriman ulang EPCS untuk tanggal yang sudah ada dulu disimpan lewat
	db_update() tanpa validate(), sehingga status seperti "Sakit R Inap" lolos
	(contoh HR-ATT-2026-86259). Sumbernya sudah ditutup di
	perbarui_attendance(); patch ini membereskan data lamanya.

	Sama seperti normalisasi_status(): status jadi On Leave, leave_type diisi
	nama di status (nama di status yang menang kalau leave_type-nya beda), dan
	status_code mengikuti Leave Type itu. Tanggal ubah dokumen tidak disentuh.
	"""
	leave_types = {
		lt.name: lt.status_code
		for lt in frappe.get_all("Leave Type", fields=["name", "status_code"])
	}

	salah = frappe.get_all(
		"Attendance",
		filters={"status": ["not in", STATUS_ATTENDANCE], "docstatus": ["<", 2]},
		fields=["name", "status", "leave_type", "status_code"],
	)

	diperbaiki, leave_type_berubah, bukan_leave_type = 0, [], []
	for att in salah:
		if att.status not in leave_types:
			bukan_leave_type.append(f"{att.name} ({att.status})")
			continue

		if att.leave_type and att.leave_type != att.status:
			leave_type_berubah.append(f"{att.name}: {att.leave_type} -> {att.status}")

		frappe.db.set_value(
			"Attendance",
			att.name,
			{
				"status": "On Leave",
				"leave_type": att.status,
				"status_code": leave_types[att.status] or att.status_code,
			},
			update_modified=False,
		)
		diperbaiki += 1

	print(f"Attendance diperbaiki: {diperbaiki}")
	if leave_type_berubah:
		print(f"leave_type diganti mengikuti status ({len(leave_type_berubah)}): {', '.join(leave_type_berubah)}")
	if bukan_leave_type:
		print(f"Status bukan Leave Type, dibiarkan ({len(bukan_leave_type)}): {', '.join(bukan_leave_type)}")
