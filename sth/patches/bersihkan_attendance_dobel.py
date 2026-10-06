import frappe

# Batas rincian yang dicetak, supaya output bench tidak kebanjiran.
BATAS_RINCIAN = 30

# Disimpan permanen tiap sekian kelompok, supaya kegagalan di tengah jalan tidak
# membuang yang sudah beres.
COMMIT_TIAP = 50


def execute(dry_run=False):
	"""Sisakan satu Attendance per employee per tanggal.

	Dobelnya datang dari tiga jalan, semuanya sudah ditutup sejak commit 5d36b01d:
	Montir, Danru, dan Satpam (NS08, NS29, NS30) dikecualikan dari cek duplikat,
	BKM Bengkel memanggil make_attendance dua kali, dan kiriman ulang mesin
	sebelum Attendance dari API jadi upsert (11 Agt 2026).

	Yang disisakan per kelompok, berurutan: yang preminya sudah masuk Salary
	Slip, yang sudah disubmit, yang punya jam masuk (kiriman mesin), yang punya
	jam pulang, lalu yang paling dulu dibuat. Jam masuk paling awal dan jam
	pulang paling akhir dari seluruh kelompok dipindah ke situ — kiriman dari
	dua mesin yang berbeda masing-masing cuma membawa sebagian. Catatan BKM
	(bkm_attendance) ikut dipindah.

	Sisanya dibatalkan kalau sudah disubmit — Employee Payment Log preminya ikut
	terhapus lewat on_cancel, karena premi itu memang terhitung dobel — atau
	dihapus kalau masih draft. Yang dibereskan diberi komentar di Attendance
	yang disisakan.

	Kelompok yang tidak bisa diputuskan sendiri dilewati dan cuma dicetak:
	status berbeda, punya Leave Application, shift berbeda, atau premi lebih
	dari satu baris yang sudah masuk Salary Slip.

	Aman dijalankan berulang: yang sudah tinggal satu tidak lagi ditemukan.

	Lihat dulu tanpa menulis:

	    bench --site <site> execute sth.patches.bersihkan_attendance_dobel.execute --kwargs "{'dry_run': 1}"
	"""
	rencana = [_rencanakan(baris) for baris in _kelompok_dobel()]

	if not dry_run:
		dikerjakan = 0
		for r in rencana:
			if r.alasan_lewat:
				continue

			try:
				frappe.db.savepoint("bersihkan_attendance")
				_bersihkan(r)
			except Exception as e:
				frappe.db.rollback(save_point="bersihkan_attendance")
				r.alasan_lewat = "gagal: {0}".format(e)
				continue

			dikerjakan += 1
			if dikerjakan % COMMIT_TIAP == 0:
				frappe.db.commit()

		frappe.db.commit()

	_cetak_ringkasan(rencana, dry_run)


def _kelompok_dobel():
	baris = frappe.db.sql("""
		SELECT
			a.name, a.employee, a.attendance_date, a.docstatus, a.status,
			a.shift, a.leave_application, a.in_time, a.out_time, a.creation,
			EXISTS (
				SELECT 1 FROM `tabEmployee Payment Log` epl
				WHERE epl.voucher_type = 'Attendance'
					AND epl.voucher_no = a.name
					AND (epl.is_paid = 1 OR IFNULL(epl.salary_slip, '') != '')
			) AS terkunci
		FROM `tabAttendance` a
		INNER JOIN (
			SELECT employee, attendance_date
			FROM `tabAttendance`
			WHERE docstatus < 2
			GROUP BY employee, attendance_date
			HAVING COUNT(*) > 1
		) dobel ON dobel.employee = a.employee AND dobel.attendance_date = a.attendance_date
		WHERE a.docstatus < 2
		ORDER BY a.employee, a.attendance_date, a.creation
	""", as_dict=True)

	kelompok = {}
	for b in baris:
		kelompok.setdefault((b.employee, b.attendance_date), []).append(b)

	return list(kelompok.values())


def _rencanakan(baris):
	baris = sorted(baris, key=lambda b: (
		-b.terkunci,
		-b.docstatus,
		b.in_time is None,
		b.out_time is None,
		b.creation,
	))

	r = frappe._dict(
		employee=baris[0].employee,
		attendance_date=baris[0].attendance_date,
		sisa=baris[0],
		buang=baris[1:],
		alasan_lewat=None,
	)

	if len({b.status for b in baris}) > 1:
		r.alasan_lewat = "status berbeda: {0}".format(", ".join(sorted({b.status for b in baris})))
	elif any(b.leave_application for b in baris):
		r.alasan_lewat = "punya Leave Application"
	elif len({b.shift for b in baris if b.shift}) > 1:
		r.alasan_lewat = "shift berbeda"
	elif sum(b.terkunci for b in baris) > 1:
		r.alasan_lewat = "premi lebih dari satu sudah masuk Salary Slip"

	semua = [r.sisa] + r.buang
	masuk = [b.in_time for b in semua if b.in_time]
	pulang = [b.out_time for b in semua if b.out_time]
	r.in_time = min(masuk) if masuk else None
	r.out_time = max(pulang) if pulang else None

	return r


def _bersihkan(r):
	sisa = r.sisa.name
	buang = [b.name for b in r.buang]

	ubah_jam = {}
	if r.in_time and r.in_time != r.sisa.in_time:
		ubah_jam["in_time"] = r.in_time
	if r.out_time and r.out_time != r.sisa.out_time:
		ubah_jam["out_time"] = r.out_time
	if ubah_jam:
		frappe.db.set_value("Attendance", sisa, ubah_jam, update_modified=False)

	# dipindah sebelum dibatalkan, kalau tidak ikut jadi docstatus 2
	frappe.db.sql("""
		UPDATE `tabBKM Attendance`
		SET parent = %(sisa)s, docstatus = %(docstatus)s
		WHERE parenttype = 'Attendance' AND parent IN %(buang)s
	""", {"sisa": sisa, "docstatus": r.sisa.docstatus, "buang": buang})

	for b in r.buang:
		if b.docstatus == 1:
			doc = frappe.get_doc("Attendance", b.name)
			doc.flags.ignore_permissions = True
			doc.cancel()
		else:
			frappe.delete_doc("Attendance", b.name, ignore_permissions=True)

	frappe.get_doc("Attendance", sisa).add_comment(
		"Info",
		"Attendance dobel di tanggal ini dibereskan: {0} dibatalkan/dihapus{1}.".format(
			", ".join(buang),
			", jam masuk/pulang digabung" if ubah_jam else "",
		),
	)


def _cetak_ringkasan(rencana, dry_run):
	beres = [r for r in rencana if not r.alasan_lewat]
	lewat = [r for r in rencana if r.alasan_lewat]

	print("{0}{1} kelompok dobel, {2} dibereskan ({3} Attendance dibuang), {4} dilewati.".format(
		"[dry run] " if dry_run else "",
		len(rencana),
		len(beres),
		sum(len(r.buang) for r in beres),
		len(lewat),
	))

	for r in beres[:BATAS_RINCIAN]:
		jam = ""
		if r.in_time != r.sisa.in_time or r.out_time != r.sisa.out_time:
			jam = "  jam {0} - {1}".format(r.in_time, r.out_time)
		print("  {0} {1}: sisakan {2}, buang {3}{4}".format(
			r.employee, r.attendance_date, r.sisa.name, ", ".join(b.name for b in r.buang), jam
		))
	if len(beres) > BATAS_RINCIAN:
		print("  ... {0} lagi".format(len(beres) - BATAS_RINCIAN))

	if lewat:
		print("Dilewati, bereskan sendiri:")
	for r in lewat:
		print("  {0} {1}: {2} — {3}".format(
			r.employee, r.attendance_date, r.alasan_lewat, ", ".join([r.sisa.name] + [b.name for b in r.buang])
		))
