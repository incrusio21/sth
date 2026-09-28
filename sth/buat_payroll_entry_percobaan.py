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


def execute(contoh=None, terapkan=0, start_date=None, end_date=None, posting_date=None, **penyaring):
	"""Susun Payroll Entry percobaan, laporkan, dan kalau diminta buat sungguhan."""
	terapkan = cint(terapkan)

	if not (start_date and end_date):
		frappe.throw("start_date dan end_date wajib diisi.")

	args = kumpulkan_penyaring(contoh, penyaring)
	args.update({
		"start_date": getdate(start_date),
		"end_date": getdate(end_date),
		"posting_date": getdate(posting_date or end_date),
	})

	doc = susun_dokumen(args)
	karyawan = doc.employees

	cetak_penyaring(args, karyawan)

	if not terapkan:
		print("\nMode laporan saja - tidak ada dokumen yang dibuat.")
		print("Jalankan ulang dengan terapkan=1 kalau susunannya sudah benar.")
		return

	doc.insert()
	print("\nPayroll Entry dibuat: {0}".format(doc.name))

	try:
		doc.submit()
	except Exception as e:
		frappe.db.rollback()
		print("\nSubmit Payroll Entry gagal, tidak ada yang tersimpan: {0}".format(e))
		print(petunjuk_gagal())
		return

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


def susun_dokumen(args):
	"""Payroll Entry yang belum disimpan, karyawannya sudah dijaring."""
	doc = frappe.new_doc("Payroll Entry")
	doc.update(args)
	doc.fill_employee_details()

	return doc


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

	if doc.docstatus == 1:
		doc.cancel()
		print("{0} dibatalkan, GL accrual-nya dibalik.".format(nama))

	if cint(benar_benar_hapus):
		frappe.delete_doc("Payroll Entry", nama)
		print("{0} dihapus.".format(nama))

	frappe.db.commit()
