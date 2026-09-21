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

	def on_cancel(self):
		self.batalkan_gl_payroll()
		super().on_cancel()

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

		if employees_data:

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

			create_salary_slips_for_employees_custom(
				employees_data,
				employee_names,
				args,
				publish_progress=False
			)

			self.reload()

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

		existing = frappe.db.get_value(
			"Payment Entry",
			{"no_payroll_entry": self.name, "docstatus": ["!=", 2]},
			"name",
		)
		if existing:
			frappe.throw(
				_("Payment Entry sudah ada: {0}").format(frappe.bold(existing))
			)

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
		"""Accrual gaji, satu baris per akun komponen.

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

		def baris(account, cost_center, debit=0, credit=0, against=None):
			return frappe._dict({
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

		post_gl_entries(gl_entries)

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

		salary_slips = self.get_sal_slip_list_draft(ss_status=0)  

		if not salary_slips:
			frappe.msgprint(_("No draft Salary Slips found"))
			return

		if len(salary_slips) > 30 or frappe.flags.enqueue_payroll_entry:
			self.db_set("status", "Queued")

			frappe.enqueue(
				submit_salary_slips_no_jv,
				timeout=3000,
				payroll_entry=self.name,
				salary_slips=salary_slips,
				publish_progress=False,
			)

			frappe.msgprint(
				_("Salary Slip submission is queued. It may take a few minutes"),
				alert=True,
				indicator="blue",
			)
		else:
			submit_salary_slips_no_jv(self.name, salary_slips, publish_progress=False)

		self.make_payroll_gl_entries()

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

def submit_salary_slips_no_jv(payroll_entry, salary_slips, publish_progress=True):
	payroll_entry = frappe.get_doc("Payroll Entry", payroll_entry)

	try:
		submitted = []
		failed = []

		count = 0

		for entry in salary_slips:
			slip = frappe.get_doc("Salary Slip", entry[0])

			try:
				slip.submit()
				submitted.append(slip.name)
			except frappe.ValidationError:
				failed.append(slip.name)

			count += 1

			if publish_progress:
				frappe.publish_progress(
					count * 100 / len(salary_slips),
					title=_("Submitting Salary Slips...")
				)

		if submitted:
			payroll_entry.db_set({
				"salary_slips_submitted": 1,
				"status": "Submitted",
				"error_message": ""
			})

		frappe.msgprint(_("Salary Slips submitted: {0}").format(len(submitted)))

	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "Payroll Submit Failed")

	finally:
		frappe.db.commit()

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


def create_salary_slips_for_employees_custom(employees_data, employee_names, args, publish_progress=True):

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
		raise

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
