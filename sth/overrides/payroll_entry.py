# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import json

import frappe
from frappe.utils import (
	DATE_FORMAT,
	add_days,
	add_to_date,
	cint,
	comma_and,
	date_diff,
	flt,
	get_link_to_form,
	getdate,
)
from frappe.query_builder.functions import Coalesce, Count

from erpnext.accounts.general_ledger import (
	make_gl_entries as post_gl_entries,
	make_reverse_gl_entries,
)
from frappe import _
from sth.accounting_sth.komponen_gaji import rincian_komponen
from hrms.payroll.doctype.payroll_entry.payroll_entry import PayrollEntry, create_salary_slips_for_employees, get_salary_structure,set_fields_to_select,set_searchfield,set_filter_conditions,set_match_conditions,remove_payrolled_employees
class PayrollEntry(PayrollEntry):

	def onload(self):
		super().onload()

		# Form menamai tombolnya "Resume ..." kalau pembuatan atau submit slipnya
		# sudah pernah dijalankan dan belum tuntas.
		if self.docstatus == 1 and not self.salary_slips_submitted:
			jumlah = dict(frappe.db.sql("""
				SELECT docstatus, COUNT(*)
				FROM `tabSalary Slip`
				WHERE payroll_entry = %s AND docstatus < 2
				GROUP BY docstatus
			""", self.name))
			self.set_onload("jumlah_slip", {
				"draft": cint(jumlah.get(0)),
				"submit": cint(jumlah.get(1)),
				"karyawan": len(self.employees),
			})

	def on_cancel(self):
		self.batalkan_gl_payroll()
		super().on_cancel()

		# Payment Ledger Entry lahir dari baris GL yang berparty - potongan BPJS
		# yang mendarat di akun bertipe Payable. Barisnya sudah didelink waktu
		# GL-nya dibalik (create_payment_ledger_entry dengan cancel=1), tapi
		# tetap ada di tabelnya, dan pemeriksaan tautan sesudah on_cancel akan
		# menolak pembatalan kalau tidak disebut di sini. ERPNext memperlakukan
		# vouchernya sendiri persis begini.
		self.ignore_linked_doctypes = tuple(self.ignore_linked_doctypes or ()) + (
			"Payment Ledger Entry",
		)

	def batalkan_gl_payroll(self):
		"""Balik GL accrual yang diposting make_payroll_gl_entries().

		Accrual gaji diposting langsung sebagai GL Entry milik Payroll Entry, bukan
		lewat Journal Entry, jadi on_cancel bawaan hrms tidak menyentuhnya sama
		sekali: yang dibatalkannya cuma Journal Entry yang tertaut, dan GL Entry
		malah dimasukkan ke ignore_linked_doctypes supaya tidak menghalangi cancel.

		Akibatnya beban gaji dan hutang gajinya tetap hidup di buku besar sesudah
		Payroll Entry-nya dibatalkan, dan dokumennya juga tidak bisa dihapus karena
		GL-nya masih menautinya.
		"""
		ada_gl = frappe.db.exists("GL Entry", {
			"voucher_type": self.doctype,
			"voucher_no": self.name,
			"is_cancelled": 0,
		})

		if ada_gl:
			make_reverse_gl_entries(voucher_type=self.doctype, voucher_no=self.name)

	def on_trash(self):
		self.hapus_gl_payroll()

	def hapus_gl_payroll(self):
		"""Buang GL Entry milik Payroll Entry ini waktu dokumennya dihapus.

		Mengikuti cara ERPNext memperlakukan vouchernya sendiri, termasuk
		penjaganya di Accounts Settings: kalau "Delete Linked Ledger Entries"
		dimatikan, GL-nya ditinggal dan penghapusan tetap dihalangi seperti
		voucher lain. Barisnya sudah bertanda batal lebih dulu lewat on_cancel,
		jadi yang dibuang di sini tidak lagi memikul saldo.
		"""
		if not frappe.db.get_single_value("Accounts Settings", "delete_linked_ledger_entries"):
			return

		gle = frappe.qb.DocType("GL Entry")
		frappe.qb.from_(gle).delete().where(
			(gle.voucher_type == self.doctype) & (gle.voucher_no == self.name)
		).run()

	@frappe.whitelist()
	def create_salary_slips(self):

		self.check_permission("write")
		self.tolak_kalau_job_slip_berjalan()

		employees_data, employee_names, args = self.bahan_pembuatan_slip()

		if employees_data:
			# Ratusan slip tidak muat dalam satu request web. Dulu semuanya dibuat
			# langsung di sini, dan untuk 500+ karyawan gunicorn membunuh worker-nya
			# di tengah jalan. Matinya lewat sys.exit, jadi finally di
			# create_salary_slips_for_employees_custom masih sempat commit: Payroll
			# Entry-nya tersubmit dengan slip setengah jadi dan salary_slips_created
			# tidak pernah dicentang. Batas 30 dan timeout-nya mengikuti hrms.
			if len(employees_data) > 30 or frappe.flags.enqueue_payroll_entry:
				self.db_set("status", "Queued")

				frappe.enqueue(
					create_salary_slips_for_employees_custom,
					job_id=self.job_id_slip("buat"),
					deduplicate=True,
					queue="long",
					timeout=max(3000, len(employees_data) * 10),
					employees_data=employees_data,
					employee_names=employee_names,
					args=args,
					publish_progress=False,
					di_antrean=True,
					enqueue_after_commit=True,
				)

				frappe.msgprint(
					_("Pembuatan Salary Slip masuk antrean. Halaman akan termuat ulang sendiri kalau sudah selesai."),
					alert=True,
					indicator="blue",
				)
			else:
				create_salary_slips_for_employees_custom(
					employees_data,
					employee_names,
					args,
					publish_progress=False
				)

				self.reload()

	def bahan_pembuatan_slip(self):
		"""Karyawan dan argumen Salary Slip, sesudah lolos penjaga BKM.

		Dipakai tombol Create Salary Slips dan lanjutkan_slip_setengah_jadi,
		supaya keduanya membuat slip dengan penjaga dan isian yang sama.
		"""
		employees_data = []

		for row in self.employees:
			employees_data.append({
				"employee": row.employee,
				"pesangon_doc": row.pesangon if self.tipe_salary == "Pesangon" else None
			})

		employee_names = [emp["employee"] for emp in employees_data]

		if self.grade == "NON STAF":
			for bkm in ["Traksi", "Panen", "Perawatan"]:
				if frappe.db.exists(f"Buku Kerja Mandor {bkm}", {
					"docstatus": ["<", 1],
					"company": self.company,
					"posting_date": ["between", [self.start_date, self.end_date]]
				}):
					frappe.throw(
						f"There are still documents Buku Kerja Mandor {bkm} "
						f"that have not been submitted for the period of "
						f"{self.start_date} to {self.end_date}"
					)

		args = frappe._dict({
			"salary_slip_based_on_timesheet": self.salary_slip_based_on_timesheet,
			"payroll_frequency": self.payroll_frequency,
			"start_date": self.start_date,
			"end_date": self.end_date,
			"company": self.company,
			"posting_date": self.posting_date,
			"deduct_tax_for_unsubmitted_tax_exemption_proof": self.deduct_tax_for_unsubmitted_tax_exemption_proof,
			"payroll_entry": self.name,
			"exchange_rate": self.exchange_rate,
			"currency": self.currency,
			"tipe_salary": self.tipe_salary
		})

		return employees_data, employee_names, args

	@frappe.whitelist()
	def fill_employee_details(self):
		filters = self.make_filters()
		print(filters)
		employees = get_employee_list_custom(filters=filters, as_dict=True, ignore_match_conditions=True)
		self.set("employees", [])

		if not employees:
			error_msg = _(
				"No employees found for the mentioned criteria:<br>Company: {0}<br> Currency: {1}<br>Payroll Payable Account: {2}"
			).format(
				frappe.bold(self.company),
				frappe.bold(self.currency),
				frappe.bold(self.payroll_payable_account),
			)
			if self.branch:
				error_msg += "<br>" + _("Branch: {0}").format(frappe.bold(self.branch))
			if self.department:
				error_msg += "<br>" + _("Department: {0}").format(frappe.bold(self.department))
			if self.designation:
				error_msg += "<br>" + _("Designation: {0}").format(frappe.bold(self.designation))
			if self.start_date:
				error_msg += "<br>" + _("Start date: {0}").format(frappe.bold(self.start_date))
			if self.end_date:
				error_msg += "<br>" + _("End date: {0}").format(frappe.bold(self.end_date))
			if self.unit:
				error_msg += "<br>" + _("Unit: {0}").format(frappe.bold(self.unit))
			frappe.throw(error_msg, title=_("No employees found"))

		self.set("employees", employees)
		self.number_of_employees = len(self.employees)
		self.update_employees_with_withheld_salaries()

		return self.get_employees_with_unmarked_attendance()

	def make_filters(self):
		filters = frappe._dict(
			company=self.company,
			branch=self.branch,
			department=self.department,
			designation=self.designation,
			grade=self.grade,
			currency=self.currency,
			start_date=self.start_date,
			end_date=self.end_date,
			payroll_payable_account=self.payroll_payable_account,
			salary_slip_based_on_timesheet=self.salary_slip_based_on_timesheet,
			unit=self.unit,
			tipe_salary=self.tipe_salary
		)

		if not self.salary_slip_based_on_timesheet:
			filters.update(dict(payroll_frequency=self.payroll_frequency))

		return filters

	
	@frappe.whitelist()
	def create_payment_entry(self):
		if self.docstatus != 1:
			frappe.throw(_("Payroll Entry harus sudah di-Submit"))

		# Satu Payroll Entry boleh dibayar beberapa Payment Entry, satu per tipe
		# atau sub tipe. Yang dijaga sisa tagihannya, di validate Payment Entry
		# (sth.hr_customize.pembayaran_payroll), bukan jumlah dokumennya.
		total_amount = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(net_pay), 0)
			FROM `tabSalary Slip`
			WHERE payroll_entry = %s AND docstatus = 1
			""",
			self.name,
		)[0][0]

		if not total_amount:
			frappe.throw(_("Tidak ada Salary Slip submitted pada Payroll Entry ini"))

		if not self.payroll_payable_account:
			frappe.throw(_("Payroll Payable Account belum diisi"))

		account_currency = frappe.db.get_value(
			"Account", self.payroll_payable_account, "account_currency"
		) or frappe.get_cached_value("Company", self.company, "default_currency")

		# ← Tidak insert, cukup return data
		return {
			"payment_type":              "Internal Transfer",
			"company":                   self.company,
			"posting_date":              frappe.utils.today(),
			"paid_to":                   self.payroll_payable_account,
			"paid_to_account_currency":  account_currency,
			"paid_amount":               total_amount,
			"received_amount":           total_amount,
			"no_payroll_entry":          self.name,
			"cost_center":               self.cost_center or None,
			"tipe_transfer":		     "Payroll Entry",
			"unit":						 self.unit,
			"remarks":                   "Payment untuk Payroll Entry: {0}".format(self.name),
		}
	
	def cost_center_per_slip(self, slips):
		"""Cost center tiap slip: karyawan mill ke stasiunnya, sisanya ke cost center dokumen.

		Beban gaji mill dipisah per stasiun sejak accrual supaya jurnal reclass
		di Costing Mill tinggal memindahkan akunnya, bukan cost center-nya.
		Karyawan non-mill tetap memakai cost center Payroll Entry.
		"""
		from sth.accounting_sth.doctype.costing_mill.costing_mill import (
			get_cost_center_stasiun,
		)

		tanpa_stasiun = [
			d.employee_name or d.employee for d in slips if d.mill and not d.stasiun
		]
		if tanpa_stasiun:
			frappe.throw(
				_("Karyawan mill berikut belum diisi Stasiun-nya: {0}").format(
					comma_and(tanpa_stasiun)
				)
			)

		hasil = {}
		tanpa_cost_center = []

		for d in slips:
			if not d.mill:
				hasil[d.name] = self.cost_center
				continue

			cost_center = get_cost_center_stasiun(d.stasiun, self.company, d.unit)
			if not cost_center:
				tanpa_cost_center.append(d.stasiun)
				continue

			hasil[d.name] = cost_center

		if tanpa_cost_center:
			frappe.throw(
				_("Stasiun berikut belum punya Cost Center (cek Detail Station Master): {0}").format(
					comma_and(sorted(set(tanpa_cost_center)))
				)
			)

		return hasil

	def get_slip_accrual(self):
		"""Slip yang diaccrual dokumen ini, lengkap dengan asal cost center-nya."""
		kolom_angsuran = (
			"IFNULL(ss.total_loan_repayment, 0)"
			if frappe.get_meta("Salary Slip").has_field("total_loan_repayment")
			else "0"
		)

		slips = frappe.db.sql("""
			SELECT
				ss.name,
				ss.employee,
				ss.employee_name,
				ss.net_pay,
				{kolom_angsuran} AS total_loan_repayment,
				e.stasiun,
				e.unit,
				IFNULL(u.mill, 0) AS mill
			FROM `tabSalary Slip` ss
			JOIN `tabEmployee` e ON e.name = ss.employee
			LEFT JOIN `tabUnit` u ON u.name = e.unit
			WHERE ss.payroll_entry = %s
			  AND ss.docstatus = 1
		""".format(kolom_angsuran=kolom_angsuran), self.name, as_dict=True)

		if not slips:
			frappe.throw(
				_("Tidak ada Salary Slip yang sudah di-submit pada Payroll Entry {0}").format(
					self.name
				)
			)

		return slips

	def make_payroll_gl_entries(self):
		"""Susun accrual gajinya, lalu posting.

		merge_entries dimatikan supaya tiap baris yang disusun tetap jadi satu
		baris GL. Kalau dibiarkan menyala, make_gl_entries menggabungkan baris
		berakun dan bercost center sama jadi satu - dan di sini itu berarti
		potongan yang seakun dengan bebannya, seperti PPh21 di company yang akun
		PPh21-nya sama dengan akun beban gaji, menempel di baris bebannya. Nilainya
		tidak hilang (debit dan kreditnya tetap dua kolom terpisah), tapi buku
		besarnya tidak lagi menunjukkan potongan itu sebagai barisnya sendiri,
		dan itu yang membuat orang harus menghitung mundur untuk tahu berapa yang
		dipotong.
		"""
		gl_entries, payable = self.susun_gl_accrual()

		post_gl_entries(gl_entries, merge_entries=False)

		frappe.msgprint(
			_("GL Entry berhasil dibuat: {0} baris beban dan potongan, "
			  "Payroll Payable {1} dikredit {2}").format(
				len(gl_entries) - 1,
				self.payroll_payable_account,
				frappe.format(payable, {"fieldtype": "Currency"}),
			),
			indicator="green",
			alert=True,
		)

	def susun_gl_accrual(self):
		"""Baris accrual gaji, satu baris per akun komponen.

		Akunnya diambil dari tabel Accounts di tiap Salary Component: earning
		didebit ke akun bebannya, deduction dikredit ke akun potongannya, dan
		sisanya - yang benar-benar dibayarkan - dikredit ke Payroll Payable.
		Dulu seluruh net pay ditumpuk di satu akun dari STH Accounting Settings,
		jadi gaji staf, gaji operator, dan potongan karyawan jatuh di akun yang
		sama dan baru terpisah (itu pun kalau sempat) waktu costing mereclass.

		Komponen yang dicentang "Not Include Net Pay" tidak ikut; aturan
		lengkapnya ada di sth.accounting_sth.komponen_gaji, yang dipakai bersama
		oleh costing supaya yang direclass persis yang diaccrual.

		Payroll Payable dikredit sebesar net pay ditambah angsuran pinjaman:
		Loan Repayment yang lahir dari tiap slip mendebit akun yang sama, jadi
		yang tersisa di situ persis sebesar yang nanti dibayar Payment Entry.

		Barisnya dipulangkan, bukan langsung diposting, supaya bisa dihitung
		lebih dulu tanpa menyentuh buku besar - itu yang dipakai patch repost
		untuk membandingkannya dengan GL yang sudah ada.
		"""
		if not self.payroll_payable_account:
			frappe.throw(_("Field 'Payroll Payable Account' belum diisi pada Payroll Entry ini"))

		slips = self.get_slip_accrual()
		cost_center = self.cost_center_per_slip(slips)
		nama_slip = [d.name for d in slips]

		debit_per_akun = {}
		for r in rincian_komponen(self.company, nama_slip, "earnings"):
			kunci = (r.account, cost_center[r.salary_slip])
			debit_per_akun[kunci] = debit_per_akun.get(kunci, 0) + flt(r.amount)

		kredit_per_akun = {}
		for r in rincian_komponen(self.company, nama_slip, "deductions"):
			kunci = (r.account, cost_center[r.salary_slip])
			kredit_per_akun[kunci] = kredit_per_akun.get(kunci, 0) + flt(r.amount)

		if not (debit_per_akun or kredit_per_akun):
			frappe.throw(
				_("Tidak ada komponen gaji yang bisa dijurnal pada Payroll Entry {0}").format(
					self.name
				)
			)

		total_net_pay = flt(sum(flt(d.net_pay) for d in slips), 2)
		total_angsuran = flt(sum(flt(d.total_loan_repayment) for d in slips), 2)
		payable = flt(total_net_pay + total_angsuran, 2)

		remarks = "Payroll Entry: {0}".format(self.name)

		party = self.party_akun_potongan(
			{a for a, _cc in debit_per_akun} | {a for a, _cc in kredit_per_akun}
		)

		def baris(account, cost_center, debit=0, credit=0, against=None):
			row = frappe._dict({
				"doctype": "GL Entry",
				"posting_date": self.posting_date,
				"account": account,
				"against": against,
				"debit": debit,
				"debit_in_account_currency": debit,
				"credit": credit,
				"credit_in_account_currency": credit,
				"voucher_type": self.doctype,
				"voucher_no": self.name,
				"company": self.company,
				"cost_center": cost_center or None,
				"remarks": remarks,
				"is_opening": "No",
			})

			if account in party:
				row.party_type, row.party = party[account]

			return row

		gl_entries = [
			baris(account, cc, debit=flt(amount, 2), against=self.payroll_payable_account)
			for (account, cc), amount in sorted(debit_per_akun.items())
			if flt(amount, 2)
		]

		gl_entries += [
			baris(account, cc, credit=flt(amount, 2), against=self.payroll_payable_account)
			for (account, cc), amount in sorted(kredit_per_akun.items())
			if flt(amount, 2)
		]

		self.setarakan_accrual(gl_entries, payable)

		against_payable = ", ".join(sorted({d.account for d in gl_entries if d.debit}))
		gl_entries.append(
			baris(self.payroll_payable_account, self.cost_center, credit=payable, against=against_payable)
		)

		return gl_entries, payable

	def party_akun_potongan(self, accounts):
		"""Party untuk akun komponen yang bertipe Payable, misalnya Hutang BPJS.

		ERPNext menolak GL Entry tanpa party di akun bertipe Receivable atau
		Payable, dan potongan BPJS karyawan memang mendarat di akun begitu -
		Hutang BPJS. Sebelum ada ini, accrual-nya berhenti dengan "Supplier is
		required against Payable account" dan seluruh jurnalnya tidak jadi.

		Supplier-nya satu untuk seluruh Payroll Entry, diisi di field Supplier
		Potongan. Itu cukup selama akun hutang potongan menunjuk satu badan
		seperti BPJS; kalau nanti ada potongan ke lawan yang berbeda dalam satu
		payroll, pilihannya pindah ke master komponennya, bukan di sini.

		Akun bertipe Receivable dilempar, bukan ditebak: yang berhutang di situ
		karyawannya sendiri (Piutang Karyawan untuk premi kontanan), sementara
		Party Type Employee di ERPNext terdaftar sebagai Payable - memasangkannya
		ke akun Receivable bukan sesuatu yang boleh diputuskan diam-diam di sini.
		"""
		tipe = tipe_akun_party(accounts)
		if not tipe:
			return {}

		receivable = sorted(a for a, t in tipe.items() if t == "Receivable")
		if receivable:
			frappe.throw(
				_("Akun komponen berikut bertipe Receivable sehingga butuh party, "
				  "dan accrual belum tahu harus memakai party apa: {0}. Ubah tipe "
				  "akunnya, atau pindahkan komponennya ke akun lain.").format(
					comma_and(receivable)
				),
				title=_("Akun Potongan Butuh Party"),
			)

		if not self.get("supplier_potongan"):
			frappe.throw(
				_("Akun komponen berikut bertipe Payable sehingga GL-nya wajib punya "
				  "party: {0}. Isi field Supplier Potongan di Payroll Entry ini.").format(
					comma_and(sorted(tipe))
				),
				title=_("Supplier Potongan Belum Diisi"),
			)

		return {a: ("Supplier", self.supplier_potongan) for a in tipe}

	def setarakan_accrual(self, gl_entries, payable):
		"""Pastikan baris komponen ketemu dengan Payroll Payable.

		Kalau penyaringnya benar, selisihnya cuma sisa pembulatan per baris dan
		ditimpakan ke baris debit terbesar. Selisih yang lebih besar dari itu
		bukan pembulatan - ada komponen yang penyaringnya tidak sama dengan yang
		dipakai Salary Slip menghitung net pay - dan lebih baik ketahuan
		sekarang daripada meninggalkan buku besar yang pincang.
		"""
		total_debit = flt(sum(flt(d.debit) for d in gl_entries), 2)
		total_kredit = flt(sum(flt(d.credit) for d in gl_entries), 2)
		selisih = flt(total_debit - total_kredit - payable, 2)

		if not selisih:
			return

		if abs(selisih) > 1:
			frappe.throw(
				_("Jurnal komponen tidak ketemu dengan net pay: beban {0} dikurangi potongan {1} "
				  "menghasilkan {2}, sedangkan net pay ditambah angsuran pinjaman {3}. "
				  "Selisihnya {4}. Periksa centang Not Include Net Pay dan Do Not Include In "
				  "Total di komponen yang dipakai periode ini.").format(
					frappe.format(total_debit, {"fieldtype": "Currency"}),
					frappe.format(total_kredit, {"fieldtype": "Currency"}),
					frappe.format(flt(total_debit - total_kredit, 2), {"fieldtype": "Currency"}),
					frappe.format(payable, {"fieldtype": "Currency"}),
					frappe.format(selisih, {"fieldtype": "Currency"}),
				),
				title=_("Accrual Gaji Tidak Seimbang"),
			)

		penerima = max(
			(d for d in gl_entries if d.debit),
			key=lambda d: flt(d.debit),
			default=None,
		)
		if not penerima:
			frappe.throw(_("Tidak ada baris beban gaji yang bisa menampung sisa pembulatan"))

		penerima.debit = flt(penerima.debit - selisih, 2)
		penerima.debit_in_account_currency = penerima.debit

	@frappe.whitelist()
	def submit_salary_slips(self):
		self.check_permission("write")
		self.tolak_kalau_job_slip_berjalan()

		salary_slips = self.get_sal_slip_list_draft(ss_status=0)

		if not salary_slips:
			# Semua slip sudah tersubmit, tapi accrual-nya bisa saja belum jadi
			# karena gagal di percobaan sebelumnya. Tombol yang sama menyusulkannya.
			if not self.posting_accrual_kalau_belum():
				frappe.msgprint(_("No draft Salary Slips found"))
			return

		# Accrual diposting di ujung submit_salary_slips_no_jv, sesudah semua slip
		# tersubmit. Dulu dipanggil di sini, sesudah enqueue: untuk lebih dari 30
		# slip job-nya belum jalan, jadi accrual menghitung dari nol slip.
		if len(salary_slips) > 30 or frappe.flags.enqueue_payroll_entry:
			self.db_set("status", "Queued")

			frappe.enqueue(
				submit_salary_slips_no_jv,
				job_id=self.job_id_slip("submit"),
				deduplicate=True,
				queue="long",
				timeout=max(3000, len(salary_slips) * 10),
				payroll_entry=self.name,
				salary_slips=salary_slips,
				publish_progress=False,
				di_antrean=True,
				enqueue_after_commit=True,
			)

			frappe.msgprint(
				_("Submit Salary Slip masuk antrean. Halaman akan termuat ulang sendiri kalau sudah selesai."),
				alert=True,
				indicator="blue",
			)
		else:
			submit_salary_slips_no_jv(self.name, salary_slips, publish_progress=False)

	def job_id_slip(self, proses):
		"""ID job antrean pembuatan ("buat") atau submit ("submit") slip dokumen ini."""
		return "payroll_entry::{0}_slip::{1}".format(proses, self.name)

	def job_slip_berjalan(self):
		"""Job slip dokumen ini yang masih menunggu atau sedang jalan di worker.

		Dipulangkan (proses, status RQ), atau None kalau tidak ada.
		"""
		from frappe.utils.background_jobs import get_job_status
		from redis.exceptions import ConnectionError as RedisConnectionError

		for proses in ("buat", "submit"):
			try:
				status = get_job_status(self.job_id_slip(proses))
			except RedisConnectionError:
				# redis antrean mati: tidak ada job yang bisa sedang jalan, dan
				# Payroll Entry kecil yang dikerjakan langsung tidak perlu ikut gagal
				return None

			if status in ("queued", "started"):
				return proses, status

		return None

	def tolak_kalau_job_slip_berjalan(self):
		"""Jangan mulai pembuatan atau submit slip selagi job sebelumnya masih hidup.

		Tombol Create dan Submit Salary Slip tetap tampil selama status Queued,
		untuk jaga-jaga job-nya mati di tengah jalan (worker di-restart paksa,
		server mati) dan statusnya tidak pernah pulih. Tapi kalau job-nya ternyata
		masih jalan, proses kedua tidak melihat slip yang belum di-commit proses
		pertama, dan slip karyawan yang sama bisa terbuat dua kali. Status job
		ditanyakan ke RQ, bukan dibaca dari field status dokumen.
		"""
		berjalan = self.job_slip_berjalan()
		if not berjalan:
			return

		proses, status = berjalan
		frappe.throw(
			_("Job {0} Salary Slip untuk Payroll Entry ini masih {1} di worker antrean long. "
			  "Tunggu sampai selesai; halaman akan termuat ulang sendiri. Kalau worker-nya "
			  "mati, RQ menandai job-nya gagal dalam beberapa menit, dan sesudah itu tombol "
			  "ini bisa dipakai lagi.").format(
				_("pembuatan") if proses == "buat" else _("submit"),
				_("menunggu giliran") if status == "queued" else _("berjalan"),
			),
			title=_("Job Masih Berjalan"),
		)

	def posting_accrual_kalau_belum(self):
		"""Posting accrual gaji sekali saja per Payroll Entry.

		Submit slip bisa diulang (sebagian slip gagal, atau accrual-nya yang
		gagal), dan tiap ulangan lewat sini. Tanpa penjaga ini, ulangan kedua
		memposting accrual seluruh slip yang sudah submit untuk kedua kalinya.
		"""
		if frappe.db.exists("GL Entry", {
			"voucher_type": self.doctype,
			"voucher_no": self.name,
			"is_cancelled": 0,
		}):
			return False

		self.make_payroll_gl_entries()
		return True

	def get_sal_slip_list_draft(self, ss_status, as_dict=False):
		"""
		Returns list of salary slips based on selected criteria
		"""

		ss = frappe.qb.DocType("Salary Slip")
		ss_list = (
			frappe.qb.from_(ss)
			.select(ss.name, ss.salary_structure)
			.where(
				(ss.docstatus == 0)
				& (ss.start_date >= self.start_date)
				& (ss.end_date <= self.end_date)
				& (ss.payroll_entry == self.name)
				& ((ss.journal_entry.isnull()) | (ss.journal_entry == ""))
				& (Coalesce(ss.salary_slip_based_on_timesheet, 0) == self.salary_slip_based_on_timesheet)
			)
		).run(as_dict=as_dict)

		return ss_list

def tipe_akun_party(accounts):
	"""Akun yang tidak boleh dijurnal tanpa party, beserta tipenya.

	Cuma Receivable dan Payable yang diperiksa ERPNext di validate_party;
	Current Liability dan kawan-kawannya lewat tanpa party.
	"""
	accounts = {a for a in accounts if a}
	if not accounts:
		return {}

	rows = frappe.get_all(
		"Account",
		filters={
			"name": ["in", sorted(accounts)],
			"account_type": ["in", ("Receivable", "Payable")],
		},
		fields=["name", "account_type"],
	)

	return {r.name: r.account_type for r in rows}

def submit_salary_slips_no_jv(payroll_entry, salary_slips, publish_progress=True, di_antrean=False):
	"""Submit slip draft, lalu posting accrual-nya kalau semuanya sudah tersubmit.

	Slip yang ditolak dicatat, bukan menghentikan sisanya; savepoint per slip
	memastikan tulisan setengah jadi dari slip yang ditolak ikut terbuang.
	Selama masih ada yang ditolak, accrual ditahan dan dokumennya ditandai
	Failed - accrual sebagian lalu disusul accrual sisanya tidak bisa dibedakan
	dari accrual ganda, jadi lebih aman menunggu semuanya lolos.
	"""
	payroll_entry = frappe.get_doc("Payroll Entry", payroll_entry)

	submitted = []
	failed = []

	try:
		count = 0

		for entry in salary_slips:
			slip = frappe.get_doc("Salary Slip", entry[0])
			titik = "submit_salary_slip"

			try:
				frappe.db.savepoint(titik)
				slip.submit()
				submitted.append(slip.name)
			except frappe.ValidationError as e:
				frappe.db.rollback(save_point=titik)
				if frappe.message_log:
					frappe.message_log.pop()
				failed.append("{0}: {1}".format(slip.name, frappe.utils.strip_html(str(e)).strip()))

			count += 1

			if publish_progress:
				frappe.publish_progress(
					count * 100 / len(salary_slips),
					title=_("Submitting Salary Slips...")
				)

		# Slip yang lolos disimpan dulu, supaya accrual yang gagal sesudah ini
		# tidak ikut membatalkan submit-nya.
		frappe.db.commit()

		if failed:
			payroll_entry.db_set({
				"status": "Failed",
				"error_message": _("{0} Salary Slip tersubmit, {1} ditolak. Accrual GL ditahan "
				                   "sampai semuanya tersubmit; perbaiki lalu klik Submit Salary Slip lagi.\n\n{2}").format(
					len(submitted), len(failed), "\n".join(failed)
				),
			})
			frappe.msgprint(
				_("{0} Salary Slip tersubmit, {1} ditolak. Lihat Error Message di Payroll Entry.").format(
					len(submitted), len(failed)
				),
				indicator="orange",
			)
			return

		payroll_entry.posting_accrual_kalau_belum()

		payroll_entry.db_set({
			"salary_slips_submitted": 1,
			"status": "Submitted",
			"error_message": ""
		})

		frappe.msgprint(_("Salary Slips submitted: {0}").format(len(submitted)))

	except Exception as e:
		frappe.db.rollback()

		if not di_antrean:
			raise

		log_payroll_failure("submission", payroll_entry, e)

	finally:
		frappe.db.commit()
		frappe.publish_realtime("completed_salary_slip_submission", user=frappe.session.user)

def get_employee_list_custom(
	filters: frappe._dict,
	searchfield=None,
	search_string=None,
	fields: list[str] | None = None,
	as_dict=True,
	limit=None,
	offset=None,
	ignore_match_conditions=False,
) -> list:
	sal_struct = get_salary_structure(
		filters.company,
		filters.currency,
		filters.salary_slip_based_on_timesheet,
		filters.payroll_frequency,
	)

	if not sal_struct:
		return []

	emp_list = get_filtered_employees_custom(
		sal_struct,
		filters,
		searchfield,
		search_string,
		fields,
		as_dict=as_dict,
		limit=limit,
		offset=offset,
		ignore_match_conditions=ignore_match_conditions,
	)

	if as_dict:
		employees_to_check = {emp.employee: emp for emp in emp_list}
	else:
		employees_to_check = {emp[0]: emp for emp in emp_list}

	return remove_payrolled_employees(employees_to_check, filters.start_date, filters.end_date)

def get_filtered_employees_custom(
	sal_struct,
	filters,
	searchfield=None,
	search_string=None,
	fields=None,
	as_dict=False,
	limit=None,
	offset=None,
	ignore_match_conditions=False,
) -> list:

	SalaryStructureAssignment = frappe.qb.DocType("Salary Structure Assignment")
	Employee = frappe.qb.DocType("Employee")

	conditions = (
		(SalaryStructureAssignment.docstatus == 1)
		& (Employee.company == filters.company)
		& (Employee.unit == filters.unit)
		& ((Employee.date_of_joining <= filters.end_date) | (Employee.date_of_joining.isnull()))
		& (SalaryStructureAssignment.salary_structure.isin(sal_struct))
		& (SalaryStructureAssignment.payroll_payable_account == filters.payroll_payable_account)
		& (filters.end_date >= SalaryStructureAssignment.from_date)
	)

	if filters.tipe_salary != "Pesangon":
		conditions &= (
			(Employee.status != "Inactive")
			& (
				(Employee.relieving_date >= filters.start_date)
				| (Employee.relieving_date.isnull())
			)
		)

	query = (
		frappe.qb.from_(Employee)
		.join(SalaryStructureAssignment)
		.on(Employee.name == SalaryStructureAssignment.employee)
		.where(conditions)
	)

	if filters.tipe_salary == "Pesangon":
		Pesangon = frappe.qb.DocType("Pesangon")
		PesangonPeriode = frappe.qb.DocType("Pesangon Periode")

		query = (
			query
			.join(Pesangon)
			.on(Pesangon.employee == Employee.name)
			.join(PesangonPeriode)
			.on(PesangonPeriode.parent == Pesangon.name)
			.where(
				(Pesangon.docstatus == 1)
				& (Pesangon.outstanding_amount > 0)
				& (PesangonPeriode.is_paid == 0)
				& (PesangonPeriode.periode >= filters.start_date)
				& (PesangonPeriode.periode <= filters.end_date)
			)
		)

		query = query.select(
			Employee.name.as_("employee"),
			Pesangon.name.as_("pesangon"),
			PesangonPeriode.name.as_("pesangon_periode"),
			PesangonPeriode.amount.as_("pesangon_amount"),
		)

	query = set_fields_to_select(query, fields)
	query = set_searchfield(query, searchfield, search_string, qb_object=Employee)
	query = set_filter_conditions(query, filters, qb_object=Employee)

	if not ignore_match_conditions:
		query = set_match_conditions(query=query, qb_object=Employee)

	if limit:
		query = query.limit(limit)

	if offset:
		query = query.offset(offset)

	print(query.get_sql())

	return query.run(as_dict=as_dict, debug=1)


# def get_filtered_employees_custom(
# 	sal_struct,
# 	filters,
# 	searchfield=None,
# 	search_string=None,
# 	fields=None,
# 	as_dict=False,
# 	limit=None,
# 	offset=None,
# 	ignore_match_conditions=False,
# ) -> list:
# 	SalaryStructureAssignment = frappe.qb.DocType("Salary Structure Assignment")
# 	Employee = frappe.qb.DocType("Employee")

# 	query = (
# 		frappe.qb.from_(Employee)
# 		.join(SalaryStructureAssignment)
# 		.on(Employee.name == SalaryStructureAssignment.employee)
# 		.where(
# 			(SalaryStructureAssignment.docstatus == 1)
# 			& (Employee.status != "Inactive")
# 			& (Employee.company == filters.company)
# 			& (Employee.unit == filters.unit)
# 			& ((Employee.date_of_joining <= filters.end_date) | (Employee.date_of_joining.isnull()))
# 			& ((Employee.relieving_date >= filters.start_date) | (Employee.relieving_date.isnull()))
# 			& (SalaryStructureAssignment.salary_structure.isin(sal_struct))
# 			& (SalaryStructureAssignment.payroll_payable_account == filters.payroll_payable_account)
# 			& (filters.end_date >= SalaryStructureAssignment.from_date)
# 		)
# 	)

# 	query = set_fields_to_select(query, fields)
# 	query = set_searchfield(query, searchfield, search_string, qb_object=Employee)
# 	query = set_filter_conditions(query, filters, qb_object=Employee)

# 	if not ignore_match_conditions:
# 		query = set_match_conditions(query=query, qb_object=Employee)

# 	if limit:
# 		query = query.limit(limit)

# 	if offset:
# 		query = query.offset(offset)

# 	return query.run(as_dict=as_dict)


def create_salary_slips_for_employees_custom(employees_data, employee_names, args, publish_progress=True, di_antrean=False):

	payroll_entry = frappe.get_cached_doc("Payroll Entry", args.payroll_entry)

	try:
		salary_slips_exist_for = get_existing_salary_slips_custom(employee_names, args)

		count = 0

		employees_to_process = [
			emp for emp in employees_data
			if emp["employee"] not in salary_slips_exist_for
		]

		for emp in employees_to_process:

			slip_data = {
				"doctype": "Salary Slip",
				"employee": emp["employee"],
				"tipe_salary": args.tipe_salary,
				**args
			}

			if args.tipe_salary == "Pesangon":
				slip_data["pesangon_doc"] = emp.get("pesangon_doc")

			frappe.get_doc(slip_data).insert()

			count += 1

			if publish_progress and employees_to_process:
				frappe.publish_progress(
					count * 100 / len(employees_to_process),
					title="Creating Salary Slips..."
				)

		payroll_entry.db_set({
			"status": "Submitted",
			"salary_slips_created": 1,
			"error_message": ""
		})

	except Exception as e:
		frappe.db.rollback()

		# Di antrean tidak ada yang menerima exception-nya: tanpa ini dokumennya
		# terkunci di Queued selamanya. Status Failed memunculkan lagi tombol
		# Create Salary Slips, dan percobaan berikutnya melewati slip yang sudah ada.
		if not di_antrean:
			raise

		log_payroll_failure("creation", payroll_entry, e)

	finally:
		frappe.db.commit()
		frappe.publish_realtime("completed_salary_slip_creation", user=frappe.session.user)

def log_payroll_failure(process, payroll_entry, error):
	error_log = frappe.log_error(
		title=_("Salary Slip {0} failed for Payroll Entry {1}").format(process, payroll_entry.name)
	)
	message_log = frappe.message_log.pop() if frappe.message_log else str(error)

	try:
		if isinstance(message_log, str):
			error_message = json.loads(message_log).get("message")
		else:
			error_message = message_log.get("message")
	except Exception:
		error_message = message_log

	error_message += "\n" + _("Check Error Log {0} for more details.").format(
		get_link_to_form("Error Log", error_log.name)
	)

	payroll_entry.db_set({"error_message": error_message, "status": "Failed"})


def get_existing_salary_slips_custom(employees, args):
	SalarySlip = frappe.qb.DocType("Salary Slip")

	conditions = (
		(SalarySlip.docstatus != 2)
		& (SalarySlip.company == args.company)
		& (SalarySlip.start_date >= args.start_date)
		& (SalarySlip.end_date <= args.end_date)
		& (SalarySlip.employee.isin(employees))
		& (SalarySlip.tipe_salary == args.tipe_salary)  
	)

	return (
		frappe.qb.from_(SalarySlip)
		.select(SalarySlip.employee)
		.distinct()
		.where(conditions)
	).run(pluck=True)


@frappe.whitelist()
def get_payroll_entry_for_payment(payroll_entry):
	"""
	Dipanggil dari Client Script Payment Entry.
	Mengembalikan detail Payroll Entry untuk auto-fill form.
	"""
	doc = frappe.get_doc("Payroll Entry", payroll_entry)

	if doc.docstatus != 1:
		frappe.throw(_("Payroll Entry {0} belum di-Submit").format(payroll_entry))

	total_amount = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(net_pay), 0)
		FROM `tabSalary Slip`
		WHERE payroll_entry = %s
		  AND docstatus = 1
		""",
		payroll_entry,
	)[0][0]

	account_currency = frappe.db.get_value(
		"Account", doc.payroll_payable_account, "account_currency"
	) or frappe.get_cached_value("Company", doc.company, "default_currency")

	return {
		"company"                 : doc.company,
		"paid_to"                 : doc.payroll_payable_account,
		"paid_to_account_currency": account_currency,
		"paid_amount"             : total_amount,
		"received_amount"         : total_amount,
		"cost_center"             : doc.cost_center or "",
		"unit"					  : doc.unit,
		"remarks"                 : "Payment untuk Payroll Entry: {0}".format(payroll_entry),
	}


@frappe.whitelist()
def balikkan_gl_payroll_batal():
	"""Balik GL accrual milik Payroll Entry yang terlanjur dibatalkan.

	Sebelum on_cancel ikut membalik GL-nya, membatalkan Payroll Entry tidak
	menyentuh accrual gaji sama sekali: dokumennya berdocstatus 2 tapi beban gaji
	dan hutang gajinya tetap hidup di buku besar.

	Tidak dijalankan sebagai patch karena jurnal baliknya memakai tanggal posting
	yang lama, dan periode itu bisa saja sudah ditutup — kapan membalikkannya
	keputusan yang menutup buku, bukan keputusan migrate:

	    bench --site <site> execute sth.overrides.payroll_entry.balikkan_gl_payroll_batal
	"""
	tertinggal = frappe.db.sql_list("""
		SELECT DISTINCT pe.name
		FROM `tabPayroll Entry` pe
		JOIN `tabGL Entry` gle
		  ON gle.voucher_type = 'Payroll Entry' AND gle.voucher_no = pe.name
		WHERE pe.docstatus = 2
		  AND gle.is_cancelled = 0
		ORDER BY pe.name
	""")

	if not tertinggal:
		print("Tidak ada Payroll Entry batal yang GL-nya masih hidup")
		return {"berhasil": [], "gagal": []}

	berhasil = []
	gagal = []

	# satu dokumen yang tertolak tidak menghentikan sisanya. yang paling sering
	# menolak adalah periode yang sudah ditutup, dan itu perlu diputuskan
	# sendiri-sendiri — bukan alasan membiarkan yang lain ikut tertinggal
	for nama in tertinggal:
		titik = "balik_gl_payroll"
		try:
			frappe.db.savepoint(titik)
			make_reverse_gl_entries(voucher_type="Payroll Entry", voucher_no=nama)
			berhasil.append(nama)
			print("OK   {0}".format(nama))
		except Exception as e:
			if frappe.message_log:
				frappe.message_log.pop()

			frappe.db.rollback(save_point=titik)
			pesan = frappe.utils.strip_html(str(e)).strip()
			gagal.append({"payroll_entry": nama, "sebab": pesan})
			print("GAGAL {0} — {1}".format(nama, pesan))

	print("")
	print("Selesai: {0} dibalik, {1} gagal".format(len(berhasil), len(gagal)))

	return {"berhasil": berhasil, "gagal": gagal}


def lanjutkan_slip_setengah_jadi(payroll_entry=None, terapkan=0):
	"""Lengkapi Salary Slip Payroll Entry yang pembuatannya terputus.

	Sebelum pembuatan slip diantrekan, Payroll Entry ratusan karyawan dibuat di
	request submit dan terputus timeout gunicorn di tengah jalan: dokumennya
	tersubmit, sebagian slipnya ada, dan salary_slips_created tidak tercentang.
	Tombol Create Salary Slips di form sudah bisa melanjutkannya; ini jalannya
	dari terminal untuk banyak dokumen sekaligus.

	Bukan patch karena membuat slip gaji keputusan payroll, bukan keputusan
	migrate - BKM atau absensi periodenya bisa saja sudah berubah sejak slip
	pertama dibuat. Bawaannya cuma melaporkan; slipnya dibuat dengan terapkan=1:

	    bench --site <site> execute sth.overrides.payroll_entry.lanjutkan_slip_setengah_jadi
	    bench --site <site> execute sth.overrides.payroll_entry.lanjutkan_slip_setengah_jadi \\
	        --kwargs "{'terapkan': 1}"
	    bench --site <site> execute sth.overrides.payroll_entry.lanjutkan_slip_setengah_jadi \\
	        --kwargs "{'payroll_entry': 'HR-PRUN-2026-00071', 'terapkan': 1}"

	Dokumen yang job slipnya masih menunggu atau berjalan di worker dilewati;
	yang berstatus Queued tapi job-nya sudah mati ikut dilengkapi. Slipnya
	dibuat langsung di sini, bukan diantrekan, jadi hasilnya terlihat begitu
	perintahnya selesai.
	Karyawan yang sudah punya slip di periode itu dilewati.
	"""
	terapkan = cint(terapkan)

	syarat = ""
	nilai = {}
	if payroll_entry:
		syarat = "AND pe.name = %(payroll_entry)s"
		nilai["payroll_entry"] = payroll_entry

	daftar = frappe.db.sql("""
		SELECT pe.name, pe.status, pe.unit, pe.start_date, pe.end_date,
			(SELECT COUNT(*) FROM `tabPayroll Employee Detail` d
			  WHERE d.parent = pe.name AND d.parenttype = 'Payroll Entry') AS jumlah_karyawan,
			(SELECT COUNT(*) FROM `tabSalary Slip` ss
			  WHERE ss.payroll_entry = pe.name AND ss.docstatus < 2) AS jumlah_slip
		FROM `tabPayroll Entry` pe
		WHERE pe.docstatus = 1
		  AND IFNULL(pe.salary_slips_created, 0) = 0
		  {syarat}
		HAVING jumlah_slip < jumlah_karyawan
		ORDER BY pe.name
	""".format(syarat=syarat), nilai, as_dict=True)

	if not daftar:
		print("Tidak ada Payroll Entry yang slipnya setengah jadi")
		return {"lengkap": [], "gagal": [], "dilewati": []}

	lengkap = []
	gagal = []
	dilewati = []

	for d in daftar:
		print("{0:22} {1:10} {2:6} {3} s/d {4}  slip {5}/{6}".format(
			d.name, d.status or "", d.unit or "", d.start_date, d.end_date,
			d.jumlah_slip, d.jumlah_karyawan,
		))

		doc = frappe.get_doc("Payroll Entry", d.name)
		berjalan = doc.job_slip_berjalan()
		if berjalan:
			print("     dilewati: job {0} slip masih {1} di worker".format(*berjalan))
			dilewati.append(d.name)
			continue

		if not terapkan:
			continue

		try:
			employees_data, employee_names, args = doc.bahan_pembuatan_slip()

			# di_antrean: kegagalan dicatat ke dokumennya (status Failed dan
			# Error Message) alih-alih menghentikan dokumen sesudahnya.
			create_salary_slips_for_employees_custom(
				employees_data, employee_names, args, publish_progress=False, di_antrean=True
			)
		except Exception as e:
			if frappe.message_log:
				frappe.message_log.pop()
			frappe.db.rollback()
			pesan = frappe.utils.strip_html(str(e)).strip()
			gagal.append({"payroll_entry": d.name, "sebab": pesan})
			print("     GAGAL {0}".format(pesan))
			continue

		doc.reload()
		jumlah_slip = frappe.db.count("Salary Slip", {"payroll_entry": d.name, "docstatus": ["<", 2]})

		if doc.salary_slips_created:
			lengkap.append(d.name)
			print("     OK    slip sekarang {0}/{1}".format(jumlah_slip, d.jumlah_karyawan))
		else:
			pesan = frappe.utils.strip_html(doc.error_message or "").strip().splitlines()
			gagal.append({"payroll_entry": d.name, "sebab": pesan[0] if pesan else doc.status})
			print("     GAGAL {0}".format(pesan[0] if pesan else doc.status))

	print("")
	if terapkan:
		print("Selesai: {0} dilengkapi, {1} gagal, {2} dilewati".format(
			len(lengkap), len(gagal), len(dilewati)
		))
	else:
		print("{0} Payroll Entry setengah jadi. Jalankan dengan terapkan=1 untuk melengkapinya.".format(
			len(daftar)
		))

	return {"lengkap": lengkap, "gagal": gagal, "dilewati": dilewati}
