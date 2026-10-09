import frappe

# Batas rincian yang dicetak, supaya output bench tidak kebanjiran.
BATAS_RINCIAN = 30

# Disimpan permanen tiap sekian Attendance, supaya kegagalan di tengah jalan
# tidak membuang yang sudah tercatat.
COMMIT_TIAP = 200


def execute(dari="2026-09-01", sampai="2026-09-30", dry_run=False, termasuk_slip_submit=False):
	"""Buat Employee Payment Log untuk Attendance Present yang belum punya EPL.

	Dibuat lewat repair_employee_payment_log, jalur yang sama dengan kiriman API
	ke Attendance yang sudah disubmit: is_holiday, premi, dan status_code dihitung
	ulang (dengan loop premi per company yang sudah dibetulkan), lalu EPL dibuat.
	Attendance yang premi-nya tetap 0 sesudah dihitung ulang memang tidak punya
	EPL — cuma dihitung dan dicetak.

	Employee yang Salary Slip September-nya sudah disubmit dilewati: EPL ber-
	payroll_date September tidak akan terbaca slip mana pun (slip Oktober cuma
	mengambil EPL lama yang ditandai salary_slip_terlewat). Mereka dicetak; pakai
	termasuk_slip_submit=1 kalau tetap mau dibuatkan.

	Tidak didaftarkan di patches.txt. Lihat dulu jumlahnya tanpa menulis:

	    bench --site <site> execute sth.patches.buat_epl_attendance_september.execute --kwargs "{'dry_run': 1}"
	"""
	attendance = frappe.db.sql(
		"""
		SELECT att.name, att.employee, att.attendance_date
		FROM `tabAttendance` att
		WHERE att.docstatus = 1
			AND att.status = 'Present'
			AND att.attendance_date BETWEEN %(dari)s AND %(sampai)s
			AND NOT EXISTS (
				SELECT 1 FROM `tabEmployee Payment Log` epl
				WHERE epl.voucher_type = 'Attendance' AND epl.voucher_no = att.name
			)
		ORDER BY att.attendance_date, att.name
		""",
		{"dari": dari, "sampai": sampai},
		as_dict=True,
	)

	slip_submit = set()
	if not termasuk_slip_submit:
		slip_submit = set(frappe.get_all(
			"Salary Slip",
			filters={"docstatus": 1, "start_date": ("<=", sampai), "end_date": (">=", dari)},
			pluck="employee",
		))

	dibuat = []
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
			doc.run_method("repair_employee_payment_log")
		except Exception as e:
			frappe.db.rollback(save_point="buat_epl_attendance")
			gagal.append((row, e))
			continue

		if frappe.db.exists("Employee Payment Log", {"voucher_type": "Attendance", "voucher_no": row.name}):
			dibuat.append((row, doc.premi_amount, doc.salary_component))
		else:
			premi_nol.append(row)

		if not dry_run and i % COMMIT_TIAP == 0:
			frappe.db.commit()

	if dry_run:
		frappe.db.rollback()
	else:
		frappe.db.commit()

	print("{0}{1} Attendance Present {2} s/d {3} tanpa EPL: {4} EPL dibuat, {5} premi 0, {6} dilewati karena slip sudah submit, {7} gagal.".format(
		"[dry run] " if dry_run else "",
		len(attendance), dari, sampai, len(dibuat), len(premi_nol), len(terlewat_slip), len(gagal),
	))

	_cetak("EPL dibuat:", dibuat, lambda d: "  {0} {1} {2}: {3} {4}".format(
		d[0].attendance_date, d[0].name, d[0].employee, d[1], d[2]))
	_cetak("Premi 0, tidak ada EPL:", premi_nol, lambda r: "  {0} {1} {2}".format(
		r.attendance_date, r.name, r.employee))
	_cetak("Dilewati, Salary Slip sudah submit:", terlewat_slip, lambda r: "  {0} {1} {2}".format(
		r.attendance_date, r.name, r.employee))

	for row, e in gagal:
		print("  GAGAL {0} {1}: {2}".format(row.name, row.employee, e))


def _cetak(judul, baris, format_baris):
	if not baris:
		return

	print(judul)
	for b in baris[:BATAS_RINCIAN]:
		print(format_baris(b))
	if len(baris) > BATAS_RINCIAN:
		print("  ... {0} lagi".format(len(baris) - BATAS_RINCIAN))
