import frappe

# Batas rincian yang dicetak, supaya output bench tidak kebanjiran.
BATAS_RINCIAN = 30

# Disimpan permanen tiap sekian BKM, supaya kegagalan di tengah jalan tidak
# membuang yang sudah tercatat.
COMMIT_TIAP = 100

DOCTYPE_BKM = (
	"Buku Kerja Mandor Panen",
	"Buku Kerja Mandor Perawatan",
	"Buku Kerja Mandor Traksi",
	"Buku Kerja Mandor Bengkel",
)


def execute(dari="2026-09-01", sampai="2026-09-30", dry_run=False):
	"""Isi mundur catatan BKM (bkm_attendance) di Attendance yang sudah ada.

	Sejak commit 5d36b01d BKM mencatat dirinya di Attendance waktu disubmit. BKM
	yang disubmit sebelumnya tidak punya catatan itu; di sini dicatatkan lewat
	make_attendance yang sama, jadi isinya persis seperti BKM baru: nomor BKM,
	kegiatan, peran, dan status versi BKM.

	Bedanya satu: Attendance yang tidak ada tidak dibuat. Membuatnya berarti
	menambah premi ke periode yang sudah berjalan — employee seperti itu cuma
	dicetak.

	Bawaannya September 2026 (posting_date BKM). Aman dijalankan berulang:
	catatan yang sudah ada tidak ditulis dua kali. Boleh sebelum atau sesudah
	bersihkan_attendance_dobel — pembersih itu ikut memindah catatannya ke
	Attendance yang disisakan.

	Butuh migrate commit 5d36b01d (field bkm_attendance di Attendance).

	Lihat dulu jumlahnya tanpa menulis:

	    bench --site <site> execute sth.patches.isi_catatan_bkm_attendance.execute --kwargs "{'dry_run': 1}"
	"""
	if not frappe.get_meta("Attendance").get_field("bkm_attendance"):
		frappe.throw("Field bkm_attendance belum ada di Attendance, jalankan migrate dulu.")

	jumlah_bkm = 0
	jumlah_catatan_awal = _jumlah_catatan()
	tanpa_attendance = []
	gagal = []

	for doctype in DOCTYPE_BKM:
		for nama in frappe.get_all(
			doctype,
			filters={"docstatus": 1, "posting_date": ("between", [dari, sampai])},
			order_by="posting_date, name",
			pluck="name",
		):
			bkm = frappe.get_doc(doctype, nama)
			try:
				frappe.db.savepoint("isi_catatan_bkm")
				for employee in bkm.make_attendance(buat_baru=False) or []:
					tanpa_attendance.append((bkm.posting_date, doctype, nama, employee))
			except Exception as e:
				frappe.db.rollback(save_point="isi_catatan_bkm")
				gagal.append((doctype, nama, e))
				continue

			jumlah_bkm += 1
			if not dry_run and jumlah_bkm % COMMIT_TIAP == 0:
				frappe.db.commit()

	jumlah_catatan = _jumlah_catatan() - jumlah_catatan_awal

	if dry_run:
		frappe.db.rollback()
	else:
		frappe.db.commit()

	print("{0}{1} BKM {2} s/d {3}, {4} catatan baru, {5} employee tanpa Attendance, {6} BKM gagal.".format(
		"[dry run] " if dry_run else "",
		jumlah_bkm, dari, sampai, jumlah_catatan, len(tanpa_attendance), len(gagal),
	))

	if tanpa_attendance:
		print("Employee tanpa Attendance (tidak dibuatkan):")
	for tanggal, doctype, nama, employee in tanpa_attendance[:BATAS_RINCIAN]:
		print("  {0} {1} {2}: {3}".format(tanggal, doctype, nama, employee))
	if len(tanpa_attendance) > BATAS_RINCIAN:
		print("  ... {0} lagi".format(len(tanpa_attendance) - BATAS_RINCIAN))

	for doctype, nama, e in gagal:
		print("  GAGAL {0} {1}: {2}".format(doctype, nama, e))


def _jumlah_catatan():
	return frappe.db.count("BKM Attendance", {"parenttype": "Attendance"})
