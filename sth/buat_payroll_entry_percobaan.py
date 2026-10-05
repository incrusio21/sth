# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

"""Buat satu Payroll Entry percobaan di server tes, lengkap sampai jurnalnya.

Dipakai untuk melihat accrual per akun komponen di desk - dokumennya sungguhan,
jadi jurnalnya bisa dibuka di report General Ledger, tidak seperti
sth/overrides/test_payroll_entry.py yang barisnya cuma hidup di memori.

Master-nya tidak dibuat di sini: company, Employee, Salary Structure, dan
Salary Component-nya memakai yang sudah ada di server itu. Yang dibuat cuma
Payroll Entry beserta Salary Slip-nya. Paling gampang menyalin penyaring dari
Payroll Entry yang sudah pernah jadi:

    bench --site <site> execute sth.buat_payroll_entry_percobaan.execute \\
        --kwargs "{'contoh': 'HR-PRUN-2026-00067', 'start_date': '2026-10-01', 'end_date': '2026-10-31'}"

Bawaannya cuma melaporkan: siapa saja karyawan yang kejaring dan apa
penyaringnya, tanpa menulis satu dokumen pun. Yang sungguhan dibuat dengan
terapkan=1:

    bench --site <site> execute sth.buat_payroll_entry_percobaan.execute \\
        --kwargs "{'contoh': 'HR-PRUN-2026-00067', 'start_date': '2026-10-01', 'end_date': '2026-10-31', 'terapkan': 1}"

Tanpa `contoh`, penyaringnya disebut satu per satu: company, unit, grade,
department, designation, tipe_salary, cost_center, payroll_payable_account.
Yang disebut langsung selalu menang atas yang disalin dari `contoh`.

Periode di server tes biasanya tidak punya BKM atau absensi, jadi semua
komponen keluar nol dan accrual-nya tidak jadi apa-apa - tidak ada yang bisa
dijurnal dari slip kosong. Untuk itu ada `tambahan`: nilai per karyawan yang
dipasang lewat Additional Salary, memakai Salary Component yang sudah ada
sehingga akunnya tetap akun yang sungguhan. `batas_karyawan` membatasi berapa
karyawan yang ikut supaya percobaannya kecil:

    bench --site <site> execute sth.buat_payroll_entry_percobaan.execute \\
        --kwargs "{'contoh': 'HR-PRUN-2026-00067', 'start_date': '2026-10-01',
                   'end_date': '2026-10-31', 'terapkan': 1, 'batas_karyawan': 2,
                   'tambahan': {'Gaji Pokok-Opr Kebun': 10000000, 'PPH21 TER': 393355}}"

Additional Salary yang dibuat menyimpan tautan ke Payroll Entry-nya, jadi
hapus() ikut membuangnya.

Untuk mencoba tombol Resume, `tahap` membentuk dokumennya setengah jadi:
resume_create menyisakan sebagian slip dan mengosongkan salary_slips_created
(tombol Resume Create Salary Slips), resume_submit membuat semua slip tapi
hanya menyubmit sebagian tanpa accrual (tombol Resume Submit Salary Slip).
`sisakan` mengatur berapa slip yang tersisa atau tersubmit (bawaannya
separuh), dan `status` bisa diisi Queued untuk mencoba jalur job terputus:

    bench --site <site> execute sth.buat_payroll_entry_percobaan.execute \\
        --kwargs "{'contoh': 'HR-PRUN-2026-00067', 'start_date': '2026-10-01',
                   'end_date': '2026-10-31', 'terapkan': 1, 'tahap': 'resume_create'}"

Yang perlu diketahui sebelum menjalankannya dengan terapkan=1:

- Periodenya harus periode yang karyawannya belum punya Salary Slip. Yang sudah
  pernah dipayroll disaring keluar oleh get_employee_list_custom, dan kalau
  semuanya tersaring dokumennya tidak jadi dibuat.
- Slip-nya disubmit lewat submit_salary_slips, jalan yang sama dengan tombol di
  form, dan submit itulah yang memposting accrual-nya. Kalau slipnya lebih dari
  30, submit-nya dilempar ke background worker - jurnalnya baru ada sesudah
  worker-nya jalan, dan skrip ini akan bilang begitu.
- Attendance yang belum ditandai bisa menggagalkan submit Payroll Entry, itu
  penjaga bawaan hrms, bukan dari sini.
"""

from contextlib import contextmanager

import frappe
from frappe.utils import cint, flt, get_url_to_form, getdate

# Penyaring yang disalin dari Payroll Entry contoh.
FIELD_DISALIN = (
	"company",
	"currency",
	"exchange_rate",
	"payroll_frequency",
	"payroll_payable_account",
	"cost_center",
	"unit",
	"grade",
	"department",
	"designation",
	"tipe_salary",
	"salary_slip_based_on_timesheet",
)


TAHAP = ("selesai", "resume_create", "resume_submit")


def execute(contoh=None, terapkan=0, start_date=None, end_date=None, posting_date=None,
            tambahan=None, batas_karyawan=None, tahap="selesai", sisakan=None, status=None,
            **penyaring):
	"""Susun Payroll Entry percobaan, laporkan, dan kalau diminta buat sungguhan."""
	terapkan = cint(terapkan)

	if tahap not in TAHAP:
		frappe.throw("tahap harus salah satu dari: {0}".format(", ".join(TAHAP)))

	if not (start_date and end_date):
		frappe.throw("start_date dan end_date wajib diisi.")

	args = kumpulkan_penyaring(contoh, penyaring)
	args.update({
		"start_date": getdate(start_date),
		"end_date": getdate(end_date),
		"posting_date": getdate(posting_date or end_date),
	})

	doc = susun_dokumen(args, batas_karyawan)
	karyawan = doc.employees

	cetak_penyaring(args, karyawan)
	cetak_tambahan(tambahan)

	if not terapkan:
		print("\nMode laporan saja - tidak ada dokumen yang dibuat.")
		print("Jalankan ulang dengan terapkan=1 kalau susunannya sudah benar.")
		return

	doc.insert()
	print("\nPayroll Entry dibuat: {0}".format(doc.name))

	if tambahan:
		buat_tambahan(doc, tambahan)

	try:
		if tahap == "selesai":
			doc.submit()
		else:
			with slip_dibuat_langsung():
				doc.submit()
	except Exception as e:
		frappe.db.rollback()
		print("\nSubmit Payroll Entry gagal, tidak ada yang tersimpan: {0}".format(e))
		print(petunjuk_gagal())
		return

	if tahap != "selesai":
		return jadikan_setengah_jadi(doc, tahap, sisakan, status)

	slip, gagal = submit_slip(doc)
	cetak_jurnal(doc.name, slip, gagal)

	return doc.name


def petunjuk_gagal():
	"""Penjaga yang paling sering menghentikan pembuatan slip di sini."""
	return (
		"\nYang biasanya menahan: Payment Log karyawan yang belum di-approve "
		"(set_employee_payment_doc di sth/overrides/salary_slip.py), Buku Kerja "
		"Mandor yang belum disubmit untuk grade NON STAF, Salary Structure "
		"Assignment yang belum menutupi periodenya, atau attendance yang belum "
		"ditandai. Semuanya penjaga dokumennya sendiri, bukan dari skrip ini."
	)


@contextmanager
def slip_dibuat_langsung():
	"""Kerjakan pembuatan slip saat itu juga, bukan lewat worker.

	Lebih dari 30 karyawan, submit Payroll Entry menitipkan pembuatan slip ke
	antrean long, dan job-nya baru jalan sesudah skrip ini commit - terlambat
	untuk dibentuk jadi setengah jadi, dan bisa bertabrakan dengan langkah
	berikutnya. Untuk tahap resume, job itu dijalankan di sini juga.
	"""
	from sth.overrides.payroll_entry import create_salary_slips_for_employees_custom

	asli = frappe.enqueue

	def enqueue(method, *args, **kwargs):
		if method is not create_salary_slips_for_employees_custom:
			return asli(method, *args, **kwargs)

		for kunci in ("queue", "timeout", "job_id", "deduplicate", "enqueue_after_commit"):
			kwargs.pop(kunci, None)
		# di_antrean dimatikan: kalau gagal, biar meledak di sini dan skripnya
		# melaporkan, bukan diam-diam menandai dokumennya Failed
		kwargs["di_antrean"] = False
		return method(**kwargs)

	frappe.enqueue = enqueue
	try:
		yield
	finally:
		frappe.enqueue = asli


def jadikan_setengah_jadi(doc, tahap, sisakan=None, status=None):
	"""Bentuk Payroll Entry yang tombolnya bernama Resume.

	resume_create: slip yang dibuat dipangkas sampai tinggal `sisakan`, dan
	salary_slips_created dikosongkan - persis yang ditinggalkan pembuatan slip
	yang terputus timeout. Tombolnya: Resume Create Salary Slips.

	resume_submit: semua slip ada, tapi hanya `sisakan` yang disubmit dan
	accrual-nya belum diposting - yang ditinggalkan job submit yang mati di
	tengah jalan. Tombolnya: Resume Submit Salary Slip.

	`sisakan` bawaannya separuh karyawan. `status` bawaannya Submitted; isi
	"Queued" untuk mencoba konfirmasi job yang terputus, atau "Failed".
	"""
	slip = frappe.get_all(
		"Salary Slip", filters={"payroll_entry": doc.name, "docstatus": 0},
		pluck="name", order_by="name",
	)
	sisakan = len(slip) // 2 if sisakan is None else min(cint(sisakan), len(slip))

	if tahap == "resume_create":
		for nama in slip[sisakan:]:
			frappe.delete_doc("Salary Slip", nama, force=1)

		doc.db_set({"salary_slips_created": 0, "status": status or "Submitted"})
		tombol = "Resume Create Salary Slips"
	else:
		for nama in slip[:sisakan]:
			frappe.get_doc("Salary Slip", nama).submit()

		doc.db_set({"salary_slips_created": 1, "status": status or "Submitted"})
		tombol = "Resume Submit Salary Slip"

	frappe.db.commit()

	jumlah = dict(frappe.db.sql("""
		SELECT docstatus, COUNT(*) FROM `tabSalary Slip`
		WHERE payroll_entry = %s AND docstatus < 2 GROUP BY docstatus
	""", doc.name))

	print("\nPayroll Entry setengah jadi: {0}".format(doc.name))
	print("  karyawan {0}, slip draft {1}, slip submit {2}, status {3}".format(
		len(doc.employees), cint(jumlah.get(0)), cint(jumlah.get(1)), status or "Submitted"
	))
	print("  tombol di form: {0}".format(tombol))
	print("  " + get_url_to_form("Payroll Entry", doc.name))
	print("\nSesudah selesai mencoba, buang dengan")
	print("  bench --site <site> execute sth.buat_payroll_entry_percobaan.hapus "
	      "--kwargs \"{{'nama': '{0}', 'benar_benar_hapus': 1}}\"".format(doc.name))

	return doc.name


def kumpulkan_penyaring(contoh, penyaring):
	"""Penyaring dari Payroll Entry contoh, ditimpa yang disebut langsung."""
	args = {}

	if contoh:
		sumber = frappe.get_doc("Payroll Entry", contoh)
		args = {f: sumber.get(f) for f in FIELD_DISALIN}

	args.update({k: v for k, v in penyaring.items() if v is not None})

	if not args.get("company"):
		frappe.throw("company wajib diisi, atau sebutkan `contoh` untuk menyalinnya.")

	args.setdefault("currency", frappe.get_cached_value("Company", args["company"], "default_currency"))
	args.setdefault("exchange_rate", 1)
	args.setdefault("payroll_frequency", "Monthly")
	args.setdefault("salary_slip_based_on_timesheet", 0)

	if not args.get("payroll_payable_account"):
		frappe.throw("payroll_payable_account wajib diisi, atau sebutkan `contoh`.")

	return args


def susun_dokumen(args, batas_karyawan=None):
	"""Payroll Entry yang belum disimpan, karyawannya sudah dijaring."""
	doc = frappe.new_doc("Payroll Entry")
	doc.update(args)
	doc.fill_employee_details()

	if cint(batas_karyawan):
		doc.employees = doc.employees[:cint(batas_karyawan)]
		doc.number_of_employees = len(doc.employees)

	return doc


def buat_tambahan(doc, tambahan):
	"""Pasang nilai lewat Additional Salary supaya slipnya tidak nol.

	Periode di server tes sering tidak punya BKM atau absensi, jadi semua
	komponen keluar nol dan accrual-nya menolak menjurnal yang kosong. Nilai di
	sini ditulis sebagai Additional Salary, bukan diisikan langsung ke baris
	slip: slip menghitung ulang komponennya dari Salary Structure tiap kali
	disimpan, dan yang diisikan tangan akan tersapu. Additional Salary memang
	jalur resminya untuk nilai sekali jalan.

	Komponennya komponen yang sudah ada - akunnya ikut master, jadi jurnalnya
	mendarat di akun yang sungguhan dipakai.

	Sengaja tidak memakai ref_doctype/ref_docname ke Payroll Entry-nya: tautan
	dinamis itu justru membuat Payroll Entry-nya tidak bisa dibatalkan lagi.
	hapus() menemukannya lewat kolom additional_salary di baris slip.

	Komponen yang dihitung sendiri oleh aplikasi - PPH21 TER dan pasangan gross
	up-nya - jangan dititipkan ke sini: nilainya akan ditulis ulang waktu slip
	menghitung pajak, sementara total_deduction slip terlanjur memakai nilai
	kiriman, dan accrual-nya menolak karena tidak ketemu dengan net pay.
	"""
	dibuat = []

	for row in doc.employees:
		for komponen, nilai in tambahan.items():
			tipe = frappe.get_cached_value("Salary Component", komponen, "type")
			if not tipe:
				frappe.throw("Salary Component {0} tidak ada di site ini.".format(komponen))

			ads = frappe.get_doc({
				"doctype": "Additional Salary",
				"employee": row.employee,
				"salary_component": komponen,
				"type": tipe,
				"amount": flt(nilai),
				"payroll_date": doc.end_date,
				"company": doc.company,
				"currency": doc.currency,
				"overwrite_salary_structure_amount": 0,
			})
			ads.insert()
			ads.submit()
			dibuat.append(ads.name)

	print("Additional Salary dibuat: {0}".format(len(dibuat)))

	return dibuat


def cetak_tambahan(tambahan):
	if not tambahan:
		return

	print("\nTAMBAHAN LEWAT ADDITIONAL SALARY (per karyawan)")
	for komponen, nilai in tambahan.items():
		tipe = frappe.get_cached_value("Salary Component", komponen, "type") or "?"
		print("  {0:9} {1:32} {2:>18,.2f}".format(tipe, komponen, flt(nilai)))


def submit_slip(doc):
	"""Submit Salary Slip-nya - langkah inilah yang memposting accrual.

	Error dari posting accrual ditangkap, bukan dibiarkan menghentikan skrip:
	submit slipnya sudah di-commit di dalam sana, jadi dokumennya tetap ada dan
	yang perlu dilihat orang justru laporannya - termasuk alasan jurnalnya tidak
	jadi. Yang paling sering: periodenya tidak punya data sama sekali sehingga
	semua komponen nol, dan susun_gl_accrual menolak menjurnal yang kosong.

	Dipulangkan daftar slipnya dan pesan gagalnya, kalau ada.
	"""
	gagal = None

	try:
		doc.submit_salary_slips()
	except Exception as e:
		# Accrual yang gagal di tengah jalan sudah sempat menulis sebagian baris
		# GL; dibuang supaya tidak ada setengah jurnal yang tertinggal. Submit
		# slipnya tidak ikut terbuang - submit_salary_slips_no_jv sudah commit
		# sendiri sebelum accrual dipanggil.
		frappe.db.rollback()
		gagal = str(e)

	slip = frappe.get_all(
		"Salary Slip",
		filters={"payroll_entry": doc.name},
		fields=["name", "employee_name", "docstatus", "net_pay"],
		order_by="name",
	)

	return slip, gagal


def cetak_penyaring(args, karyawan):
	print("PENYARING")
	for kunci in ("company", "unit", "grade", "department", "designation", "tipe_salary",
	              "payroll_frequency", "currency", "cost_center", "payroll_payable_account",
	              "start_date", "end_date", "posting_date"):
		if args.get(kunci):
			print("  {0:26} {1}".format(kunci, args[kunci]))

	print("\nKARYAWAN KEJARING: {0}".format(len(karyawan)))
	for d in karyawan:
		print("  {0:14} {1}".format(d.employee, d.employee_name))


def cetak_jurnal(nama, slip, gagal=None):
	"""Cetak slip yang jadi dan jurnal yang terposting, plus tautan ke desk."""
	terkirim = [d for d in slip if d.docstatus == 1]

	print("\nSALARY SLIP: {0} dibuat, {1} submit".format(len(slip), len(terkirim)))
	for d in slip:
		print("  {0:40} {1:28} docstatus {2}  net {3:,.2f}".format(
			d.name, d.employee_name, d.docstatus, flt(d.net_pay)
		))

	if terkirim and not any(flt(d.net_pay) for d in terkirim):
		print("\nSemua slipnya nol - periode ini tidak punya data gaji apa pun di site ini.")
		print("Jurnalnya tidak bisa dibuat; pilih periode lain, lalu buang yang ini dengan")
		print("  bench --site <site> execute sth.buat_payroll_entry_percobaan.hapus --kwargs \"{{'nama': '{0}'}}\"".format(nama))

	if gagal:
		print("\nAccrual-nya tidak jadi diposting: {0}".format(gagal))

	gl = frappe.get_all(
		"GL Entry",
		filters={"voucher_type": "Payroll Entry", "voucher_no": nama, "is_cancelled": 0},
		fields=["account", "cost_center", "debit", "credit"],
		order_by="debit desc, credit desc",
	)

	if not gl:
		print("\nBelum ada GL Entry. Kalau slipnya lebih dari 30, submit-nya dilempar ke")
		print("background worker - tengok lagi sesudah worker-nya jalan.")
		return

	print("\nJURNAL")
	print("  {0:52} {1:18} {2:>18} {3:>18}".format("AKUN", "COST CENTER", "DEBIT", "KREDIT"))
	for d in gl:
		print("  {0:52} {1:18} {2:>18,.2f} {3:>18,.2f}".format(
			d.account, d.cost_center or "", flt(d.debit), flt(d.credit)
		))
	print("  {0:52} {1:18} {2:>18,.2f} {3:>18,.2f}".format(
		"TOTAL", "", sum(flt(d.debit) for d in gl), sum(flt(d.credit) for d in gl)
	))

	print("\nLihat di desk:")
	print("  " + get_url_to_form("Payroll Entry", nama))
	print("  " + frappe.utils.get_url(
		"/app/query-report/General Ledger?voucher_no={0}".format(nama)
	))


def hapus(nama, benar_benar_hapus=0):
	"""Buang Payroll Entry percobaan berikut slip dan jurnalnya.

	Cancel-nya membalik GL accrual lewat batalkan_gl_payroll dan menghapus
	Salary Slip yang tertaut - itu perilaku dokumennya sendiri, bukan sesuatu
	yang dikarang di sini. Dengan benar_benar_hapus=1 dokumennya ikut dihapus,
	tapi barisan GL-nya baru benar-benar terbuang kalau "Delete Linked Ledger
	Entries" di Accounts Settings menyala.

	    bench --site <site> execute sth.buat_payroll_entry_percobaan.hapus \\
	        --kwargs "{'nama': 'HR-PRUN-2026-00070', 'benar_benar_hapus': 1}"
	"""
	doc = frappe.get_doc("Payroll Entry", nama)

	# Dikumpulkan sebelum cancel: slipnya ikut terhapus waktu Payroll Entry
	# dibatalkan, dan sesudah itu tidak ada lagi yang menunjuk Additional Salary
	# yang dibuat untuk percobaan ini.
	tambahan = cari_tambahan(nama)

	if doc.docstatus == 1:
		doc.cancel()
		# Di-commit di sini supaya pembatalannya tetap berlaku walaupun langkah
		# penghapusan di bawah tersandung sesuatu.
		frappe.db.commit()
		print("{0} dibatalkan, GL accrual-nya dibalik.".format(nama))

	if cint(benar_benar_hapus):
		buang_payment_ledger(nama)
		frappe.delete_doc("Payroll Entry", nama)
		print("{0} dihapus.".format(nama))

	for ads in tambahan:
		frappe.get_doc("Additional Salary", ads).cancel()

		if cint(benar_benar_hapus):
			frappe.delete_doc("Additional Salary", ads)

		print("Additional Salary {0} dibuang.".format(ads))

	frappe.db.commit()


def buang_payment_ledger(nama):
	"""Buang Payment Ledger Entry milik percobaan ini sebelum dokumennya dihapus.

	Baris itu lahir dari potongan yang mendarat di akun bertipe Payable, misalnya
	Hutang BPJS dengan party Supplier Potongan. Waktu GL-nya dibalik, barisnya
	cuma ditandai delink, bukan dihapus - dan pemeriksaan tautan waktu menghapus
	dokumen hanya melewatkan yang docstatus-nya cancelled, sementara PLE tetap
	submitted. Jadi tanpa ini Payroll Entry percobaan tidak akan pernah bisa
	dihapus, cuma bisa dibatalkan.

	Sengaja hanya di skrip percobaan: buku besar sungguhan tidak seharusnya
	kehilangan jejak begini, dan di sana pembatalan memang sudah cukup.
	"""
	rows = frappe.get_all(
		"Payment Ledger Entry",
		filters={"voucher_type": "Payroll Entry", "voucher_no": nama},
		pluck="name",
	)

	if not rows:
		return

	frappe.db.delete("Payment Ledger Entry", {"name": ["in", rows]})
	print("Payment Ledger Entry dibuang: {0}".format(len(rows)))


def cari_tambahan(nama):
	"""Additional Salary yang terpakai di slip Payroll Entry ini."""
	slip = frappe.get_all("Salary Slip", filters={"payroll_entry": nama}, pluck="name")
	if not slip:
		return []

	return list({
		d.additional_salary
		for d in frappe.get_all(
			"Salary Detail",
			filters={"parent": ["in", slip], "additional_salary": ["is", "set"]},
			fields=["additional_salary"],
		)
		if d.additional_salary
	})
