import frappe
from frappe.utils import flt

# Batas rincian yang dicetak, supaya output bench tidak kebanjiran.
BATAS_RINCIAN = 30

# Disimpan permanen tiap sekian Attendance, supaya kegagalan di tengah jalan
# tidak membuang yang sudah tercatat.
COMMIT_TIAP = 200


def execute(dari="2026-09-01", sampai="2026-09-30", dry_run=False, termasuk_slip_submit=False, employee=None):
	"""Buat Employee Payment Log untuk Attendance Present yang belum punya EPL.

	Jabatan di Attendance dicek ulang dulu: designation diambil dari jabatan
	employee pada attendance_date, lalu ditimpa ke Attendance kalau beda atau
	kosong. Jabatan pada tanggal itu dibaca dari riwayat Employee Promotion /
	Employee Transfer — kalau ada perubahan jabatan sesudah attendance_date,
	yang dipakai jabatan sebelum perubahan pertama; kalau tidak ada, jabatan
	Employee sekarang.

	Sesudah itu lewat repair_employee_payment_log, jalur yang sama dengan
	kiriman API ke Attendance yang sudah disubmit: is_holiday, premi, dan
	status_code dihitung ulang dari jabatan tadi, lalu EPL dibuat. Attendance
	yang premi-nya tetap 0 memang tidak punya EPL — cuma dihitung dan dicetak.

	Employee yang Salary Slip September-nya sudah disubmit dilewati: EPL ber-
	payroll_date September tidak akan terbaca slip mana pun (slip Oktober cuma
	mengambil EPL lama yang ditandai salary_slip_terlewat). Mereka dicetak; pakai
	termasuk_slip_submit=1 kalau tetap mau dibuatkan.

	employee membatasi ke employee tertentu: satu ID atau list ID. Kosong berarti
	semua employee.

	Tidak didaftarkan di patches.txt. Lihat dulu jumlahnya tanpa menulis:

	    bench --site <site> execute sth.patches.buat_epl_attendance_september.execute --kwargs "{'dry_run': 1}"
	    bench --site <site> execute sth.patches.buat_epl_attendance_september.execute --kwargs "{'dry_run': 1, 'employee': ['EMP-001', 'EMP-002']}"
	"""
	if isinstance(employee, str):
		employee = [employee]

	attendance = frappe.db.sql(
		"""
		SELECT att.name, att.employee, att.attendance_date
		FROM `tabAttendance` att
		WHERE att.docstatus = 1
			AND att.status = 'Present'
			AND att.attendance_date BETWEEN %(dari)s AND %(sampai)s
			{filter_employee}
			AND NOT EXISTS (
				SELECT 1 FROM `tabEmployee Payment Log` epl
				WHERE epl.voucher_type = 'Attendance' AND epl.voucher_no = att.name
			)
		ORDER BY att.attendance_date, att.name
		""".format(filter_employee="AND att.employee IN %(employee)s" if employee else ""),
		{"dari": dari, "sampai": sampai, "employee": tuple(employee or [])},
		as_dict=True,
	)

	slip_submit = set()
	if not termasuk_slip_submit:
		filters = {"docstatus": 1, "start_date": ("<=", sampai), "end_date": (">=", dari)}
		if employee:
			filters["employee"] = ("in", employee)

		slip_submit = set(frappe.get_all("Salary Slip", filters=filters, pluck="employee"))

	dibuat = []
	jabatan_diganti = []
	premi_nol = []
	terlewat_slip = []
	gagal = []

	for i, row in enumerate(attendance, 1):
		if row.employee in slip_submit:
			terlewat_slip.append(row)
			continue

		try:
			frappe.db.savepoint("buat_epl_attendance")
			doc = frappe.get_doc("Attendance", row.name)
			jabatan_lama, premi_lama = doc.designation, flt(doc.premi_amount)

			jabatan = jabatan_pada_tanggal(doc.employee, doc.attendance_date)
			if not jabatan:
				raise frappe.ValidationError("Employee tidak punya jabatan")

			# repair_employee_payment_log menulis ulang seluruh field lewat
			# db_update, jadi designation cukup diganti di objeknya
			doc.designation = jabatan
			doc.run_method("repair_employee_payment_log")
		except Exception as e:
			frappe.db.rollback(save_point="buat_epl_attendance")
			gagal.append((row, e))
			continue

		if jabatan_lama != doc.designation:
			jabatan_diganti.append((row, jabatan_lama, doc.designation, premi_lama, flt(doc.premi_amount)))

		if frappe.db.exists("Employee Payment Log", {"voucher_type": "Attendance", "voucher_no": row.name}):
			dibuat.append((row, doc.designation, doc.premi_amount, doc.salary_component))
		else:
			premi_nol.append((row, doc.designation))

		if not dry_run and i % COMMIT_TIAP == 0:
			frappe.db.commit()

	if dry_run:
		frappe.db.rollback()
	else:
		frappe.db.commit()

	print("{0}{1} Attendance Present {2} s/d {3} tanpa EPL: {4} jabatan diganti, {5} EPL dibuat, {6} premi 0, {7} dilewati karena slip sudah submit, {8} gagal.".format(
		"[dry run] " if dry_run else "",
		len(attendance), dari, sampai, len(jabatan_diganti), len(dibuat),
		len(premi_nol), len(terlewat_slip), len(gagal),
	))

	_cetak("Jabatan diganti (jabatan lama -> baru, premi lama -> baru):", jabatan_diganti,
		lambda d: "  {0} {1} {2}: {3} -> {4}, {5} -> {6}".format(
			d[0].attendance_date, d[0].name, d[0].employee, d[1] or "(kosong)", d[2], d[3], d[4]))
	_cetak("EPL dibuat:", dibuat, lambda d: "  {0} {1} {2} ({3}): {4} {5}".format(
		d[0].attendance_date, d[0].name, d[0].employee, d[1], d[2], d[3]))
	_cetak("Premi 0, tidak ada EPL:", premi_nol, lambda d: "  {0} {1} {2} ({3})".format(
		d[0].attendance_date, d[0].name, d[0].employee, d[1]))
	_cetak("Dilewati, Salary Slip sudah submit:", terlewat_slip, lambda r: "  {0} {1} {2}".format(
		r.attendance_date, r.name, r.employee))

	for row, e in gagal:
		print("  GAGAL {0} {1}: {2}".format(row.name, row.employee, e))


def jabatan_pada_tanggal(employee, tanggal):
	"""Jabatan employee pada tanggal itu.

	Perubahan jabatan pertama sesudah tanggal itu menyimpan jabatan sebelumnya
	di kolom current; kalau tidak ada perubahan sesudahnya, jabatan Employee
	sekarang yang berlaku.
	"""
	sesudahnya = frappe.db.sql(
		"""
		SELECT eph.current
		FROM `tabEmployee Update Log` eul
		JOIN `tabEmployee Property History` eph
			ON eph.parenttype = eul.voucher_type AND eph.parent = eul.voucher_no
		WHERE eul.employee = %(employee)s
			AND eul.posting_date > %(tanggal)s
			AND eph.fieldname = 'designation'
		ORDER BY eul.posting_date, eul.creation
		LIMIT 1
		""",
		{"employee": employee, "tanggal": tanggal},
	)
	if sesudahnya and sesudahnya[0][0]:
		return sesudahnya[0][0]

	return frappe.db.get_value("Employee", employee, "designation")


def _cetak(judul, baris, format_baris):
	if not baris:
		return

	print(judul)
	for b in baris[:BATAS_RINCIAN]:
		print(format_baris(b))
	if len(baris) > BATAS_RINCIAN:
		print("  ... {0} lagi".format(len(baris) - BATAS_RINCIAN))
