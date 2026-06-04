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

from erpnext.accounts.general_ledger import make_gl_entries as post_gl_entries
from frappe import _
from hrms.payroll.doctype.payroll_entry.payroll_entry import PayrollEntry, create_salary_slips_for_employees, get_salary_structure,set_fields_to_select,set_searchfield,set_filter_conditions,set_match_conditions,remove_payrolled_employees
class PayrollEntry(PayrollEntry):
	
	def get_salary_components(self, component_type):
		salary_slips = self.get_sal_slip_list(ss_status=1, as_dict=True)

		if salary_slips:
			ss = frappe.qb.DocType("Salary Slip")
			ssd = frappe.qb.DocType("Salary Detail")
			salary_components = (
				frappe.qb.from_(ss)
				.join(ssd)
				.on(ss.name == ssd.parent)
				.select(
					ssd.salary_component,
					ssd.amount,
					ssd.parentfield,
					ssd.additional_salary,
					ssd.account_list_rate,
					ss.salary_structure,
					ss.employee,
				)
				.where((ssd.parentfield == component_type) & (ss.name.isin([d.name for d in salary_slips])))
			).run(as_dict=True)

			return salary_components
		  
	def get_salary_component_total(
		self,
		component_type=None,
		employee_wise_accounting_enabled=False,
	):
		salary_components = self.get_salary_components(component_type)
		if salary_components:
			component_dict = {}
			account_dict = {}

			for item in salary_components:
				if not self.should_add_component_to_accrual_jv(component_type, item):
					continue
				
				employee_cost_centers = self.get_payroll_cost_centers_for_employee(
					item.employee, item.salary_structure
				)
				employee_advance = self.get_advance_deduction(component_type, item)

				for cost_center, percentage in employee_cost_centers.items():

					acc_dict = json.loads(item.account_list_rate or "{}")
					for acc, value in acc_dict.items():
						accounting_key = (acc, cost_center)
						acc_against_cost_center = flt(value) * percentage / 100
						account_dict[accounting_key] = account_dict.get(accounting_key, 0) + acc_against_cost_center

						item.amount -= acc_against_cost_center

					if not item.amount:
						continue

					amount_against_cost_center = flt(item.amount) * percentage / 100
					
					if employee_advance:
						self.add_advance_deduction_entry(
							item, amount_against_cost_center, cost_center, employee_advance
						)
					else:
						key = (item.salary_component, cost_center)
						component_dict[key] = component_dict.get(key, 0) + amount_against_cost_center

					if employee_wise_accounting_enabled:
						self.set_employee_based_payroll_payable_entries(
							component_type, item.employee, amount_against_cost_center
						)

			account_details = self.get_account(account_dict, component_dict=component_dict)

			return account_details 
		
	def get_account(self, account_dict, component_dict=None):
		for key, amount in component_dict.items():
			component, cost_center = key
			account = self.get_salary_component_account(component)
			accounting_key = (account, cost_center)

			account_dict[accounting_key] = account_dict.get(accounting_key, 0) + amount

		return account_dict
	

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
	
	def make_payroll_gl_entries(self):
		"""
		Membuat GL Entry untuk Payroll Entry:
		  - Debit  : Akun 6211002 (Gaji, Tunjangan dan Manfaat) sesuai company
		  - Credit : payroll_payable_account
		Nilai diambil dari total net_pay seluruh Salary Slip yang terhubung.
		Hanya menghasilkan 2 baris GL Entry.
		"""

		# ── 1. Hitung total dari semua Salary Slip yang terhubung ──────────────
		total_amount = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(net_pay), 0)
			FROM `tabSalary Slip`
			WHERE payroll_entry = %s
			  AND docstatus = 1
			""",
			self.name,
		)[0][0]

		if not total_amount:
			frappe.throw(
				_("Tidak ada Salary Slip yang sudah di-submit pada Payroll Entry {0}").format(
					self.name
				)
			)

		# ── 2. Ambil akun debit 6211002 berdasarkan company ───────────────────
		debit_account = frappe.db.get_value(
			"Account",
			{"account_number": "6211002", "company": self.company},
			"name",
		)

		if not debit_account:
			frappe.throw(
				_("Akun dengan nomor 6211002 tidak ditemukan untuk perusahaan {0}").format(
					self.company
				)
			)

		# ── 3. Validasi akun kredit ────────────────────────────────────────────
		if not self.payroll_payable_account:
			frappe.throw(_("Field 'Payroll Payable Account' belum diisi pada Payroll Entry ini"))

		# ── 4. Buat 2 baris GL Entry ───────────────────────────────────────────
		remarks = "Payroll Entry: {0}".format(self.name)

		gl_entries = [
			# Baris 1 — DEBIT (Beban Gaji)
			frappe._dict({
				"doctype": "GL Entry",
				"posting_date": self.posting_date,
				"account": debit_account,
				"against": self.payroll_payable_account,
				"debit": total_amount,
				"debit_in_account_currency": total_amount,
				"credit": 0,
				"credit_in_account_currency": 0,
				"voucher_type": self.doctype,
				"voucher_no": self.name,
				"company": self.company,
				"cost_center": self.cost_center or None,
				"remarks": remarks,
				"is_opening": "No",
			}),
			# Baris 2 — CREDIT (Hutang Gaji)
			frappe._dict({
				"doctype": "GL Entry",
				"posting_date": self.posting_date,
				"account": self.payroll_payable_account,
				"against": debit_account,
				"debit": 0,
				"debit_in_account_currency": 0,
				"credit": total_amount,
				"credit_in_account_currency": total_amount,
				"voucher_type": self.doctype,
				"voucher_no": self.name,
				"company": self.company,
				"cost_center": self.cost_center or None,
				"remarks": remarks,
				"is_opening": "No",
			}),
		]

		post_gl_entries(gl_entries)

		frappe.msgprint(
			_("GL Entry berhasil dibuat: Debit {0} | Credit {1} | Total {2}").format(
				debit_account,
				self.payroll_payable_account,
				frappe.format(total_amount, {"fieldtype": "Currency"}),
			),
			indicator="green",
			alert=True,
		)

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

	return query.run(as_dict=as_dict)


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