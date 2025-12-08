# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import json

import frappe
from frappe import _, scrub
from frappe.utils import add_days, flt, getdate, get_first_day_of_week, get_last_day_of_week, month_diff, now
from frappe.query_builder.functions import Count, IfNull

from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip, get_salary_component_data
from hrms.payroll.doctype.payroll_period.payroll_period import (
	get_period_factor,
)
from hrms.payroll.doctype.salary_slip.salary_slip_loan_utils import (\
	set_loan_repayment,
)

from datetime import datetime, timedelta

class SalarySlip(SalarySlip):
	def on_submit(self):
		super().on_submit()
		self.update_payment_related("Employee Payment Log", "payment_log_list")
		self.update_payment_related("Loan Repayment", "loan_repayment_list")

	def on_cancel(self):
		super().on_submit()

		self.update_payment_related("Employee Payment Log", "payment_log_list", cancel=1)
		self.update_payment_related("Loan Repayment", "loan_repayment_list", cancel=1)

	def update_payment_related(self, doctype, list_field, cancel=0):
		dt = frappe.qb.DocType(doctype)

		query = (
			frappe.qb.update(dt)
			.set(dt.is_paid, 0 if cancel else 1)
			.set(dt.salary_slip, "" if cancel else self.name)
			.set(dt.modified, now())
			.set(dt.modified_by, frappe.session.user)
			.where(
				(dt.salary_slip == self.name) if cancel
				else (dt.name.isin(getattr(self, list_field)))
			)
		)

		query.run()

	def get_working_days_details(self, lwp=None, for_preview=0):
		super().get_working_days_details(lwp, for_preview)

		self.not_check_out = self._get_not_out_attendance_days()
		
		self.calculate_holidays()

	def calculate_holidays(self):
		list_attendance = self._get_attendance_days()
		holidays = self.get_holidays_for_employee(self.actual_start_date, self.actual_end_date)

		self.holiday_days = 0
		week_start = week_end = None
		actual_start, actual_end = getdate(self.actual_start_date), getdate(self.actual_end_date)

		for h in holidays:
			# jika tidak terdapat tanggal akhir atau 
			# holidays sudah tidak masuk dalam minggu terpilih
			if not week_end or h > week_end:
				# cek agar waktu mulai dan berakhir tidam melampaui bulan ini
				week_start = max(get_first_day_of_week(h), actual_start)
				week_end = min(get_last_day_of_week(h), actual_end)
			else:
				# skip krn holidays sudah di hitung untuk minggu ini
				continue
			
			current_week_holiday = 0
			att_exist = False
			allWeekOff = True 
			# cek tanggal pada minggu ini 
			# ada berapa holidays dan 
			# apakah ada att atau minggu libur
			current_date = week_start
			while current_date <= week_end:
				if current_date not in holidays:
					allWeekOff = False
				else:
					current_week_holiday += 1
				
				if current_date in list_attendance:
					att_exist = True
				
				current_date = add_days(current_date, 1)
			
			# jika seluruh hari dalam satu minggu libur 
			# atau terdapat attendance tambahkan holidays
			if allWeekOff or att_exist:
				self.holiday_days += current_week_holiday

	def _get_not_out_attendance_days(self) -> float:
		Attendance = frappe.qb.DocType("Attendance")
		query = (
			frappe.qb.from_(Attendance)
			.select(Count("*"))
			.where(
				(Attendance.attendance_date.between(self.actual_start_date, self.actual_end_date))
				& (Attendance.employee == self.employee)
				& (Attendance.docstatus == 1)
				& (Attendance.status == "Present")
				& (Attendance.out_time.isnull())
			)
		)

		return query.run()[0][0]
	
	def _get_attendance_days(self) -> list:
		Attendance = frappe.qb.DocType("Attendance")
		query = (
			frappe.qb.from_(Attendance)
			.select(Attendance.attendance_date)
			.where(
				(Attendance.attendance_date.between(self.start_date, self.actual_end_date))
				& (Attendance.employee == self.employee)
				& (Attendance.docstatus == 1)
				& (Attendance.status.isin(["Present"]))
			)
		).run()

		return [row[0] for row in query]
	
	def calculate_net_pay(self, skip_tax_breakup_computation: bool = False):
		# agar payment log selalu generate ulang
		self.payment_log_list = []
		self.loan_repayment_list = []
		
		def set_gross_pay_and_base_gross_pay():
			self.gross_pay = self.get_component_totals("earnings", depends_on_payment_days=1)
			self.base_gross_pay = flt(
				flt(self.gross_pay) * flt(self.exchange_rate), self.precision("base_gross_pay")
			)

		if not getattr(self, "_employee_payment_log", None):
			self.set_employee_payment_doc()

		# tambahan untuk tutup buku. krn jika tidak
		self.set_addons_premi()

		# hapus component against terlebih dahulu untuk d create ulang
		self.remove_flexibel_payment()
		self.calculate_employee_payment()

		if self.salary_structure:
			self.calculate_component_amounts("earnings")

		# get remaining numbers of sub-period (period for which one salary is processed)
		if self.payroll_period:
			self.remaining_sub_periods = get_period_factor(
				self.employee,
				self.start_date,
				self.end_date,
				self.payroll_frequency,
				self.payroll_period,
				joining_date=self.joining_date,
				relieving_date=self.relieving_date,
			)[1]

		set_gross_pay_and_base_gross_pay()

		if self.salary_structure:
			self.calculate_component_amounts("deductions")

		set_loan_repayment(self)

		self.calculate_subsidy_loan()
		
		self.set_precision_for_component_amounts()
		self.set_net_pay()
		if not skip_tax_breakup_computation:
			self.compute_income_tax_breakup()

	def set_employee_payment_doc(self) -> None:
		# get structur first
		if not getattr(self, "_salary_structure_doc", None):
			self.set_salary_structure_doc()

		epl = frappe.qb.DocType("Employee Payment Log")
		emp_pl = (
			frappe.qb.from_(epl)
			.select(epl.name, epl.account, epl.salary_component, epl.type, epl.against_salary_component, epl.amount, epl.status)
			.where(
				(epl.employee == self.employee)
				& (epl.company == self.company)
				& (epl.payroll_date.between(self.start_date, self.end_date))
				& (epl.is_paid != 1)
			)
			.for_update()
		).run(as_dict=1)
		
		self._employee_payment, self._against_employee_payment = {}, {}
		for pl in emp_pl:
			# throw jika status payment log belum approved (document belum fix)
			if pl.status != "Approved":
				frappe.throw("There are still Payment Logs for Employee {} that have not been Approved".format(self.employee))

			# set key berdasarkan component dan nama table
			key = (pl.salary_component, scrub(f"{pl.type}s"))
			self._employee_payment.setdefault(key, {
				"account": {},
				"amount": 0,
			})

			if pl.account:
				self._employee_payment[key]["account"].setdefault(pl.account, 0)                    
				self._employee_payment[key]["account"][pl.account] += pl.amount

			self._employee_payment[key]["amount"] += pl.amount

			if pl.against_salary_component:
				key_against = pl.against_salary_component
				self._against_employee_payment.setdefault(key_against, 0)
				self._against_employee_payment[key_against] += (
					pl.amount if pl.type == "deductions" else -pl.amount
				)

			self.payment_log_list.append(pl.name)

	def set_addons_premi(self):
		if getdate(self.end_date) != getdate(self.actual_end_date):
			return
		
		designation = frappe.get_cached_doc("Designation", self.designation)
		addons_premi = 0
		for premi in designation.premi:
			if premi.company == self.company and premi.premi_type not in ("Tutup Buku"):
				continue
			
			addons_premi += premi.amount or 0

		# jika premi tambahan masukkan dalam employee payment log
		if addons_premi:
			key = (designation.salary_component, "earnings")
			self._employee_payment.setdefault(key, {
				"account": {},
				"amount": 0,
			})

			self._employee_payment[key]["amount"] += addons_premi
		

	def remove_flexibel_payment(self):
		removed_component = []
		for component_type in ["earnings", "deductions"]:
			removed_component.extend(self.get(component_type, {"is_flexibel_payment": 1}))
		
		for d in removed_component:
			self.remove(d)

	def calculate_employee_payment(self):	
		for (component, component_type), value in self._employee_payment.items():
			self.add_component_custom(
				component, 
				component_type, 
				abs(value["amount"]),
				{"account_rate": json.dumps(value["account"])}
			)

		for component, total_amount in self._against_employee_payment.items():
			component_type = "earnings" if total_amount > 0 else "deductions"
			self.add_component_custom(
				component, 
				component_type, 
				abs(total_amount)
			)

	def calculate_subsidy_loan(self):
		self.add_repaymant_subsidy()
		if self.get("loans"):
			self.add_loans_monthly_subsidy()

	def add_repaymant_subsidy(self):
		lp = frappe.qb.DocType("Loan Repayment")

		query = (
			frappe.qb.from_(lp)
			.select(lp.name, lp.subsidy_component, lp.against_subsidy_component, lp.amount_paid)
			.where(
				(IfNull(lp.subsidy_component, "") != "")
				&(lp.applicant == self.employee)
				& (lp.company == self.company)
				& (lp.docstatus == 1)
				& (lp.is_paid == 0)
				& (lp.posting_date <= self.end_date)
			)
			.for_update()
		)

		subsidy_list = query.run(as_dict=True)

		subsidy_component, against_component = {}, {}

		for sc in subsidy_list:
			subsidy_component.setdefault(sc.subsidy_component, 0)
			against_component.setdefault(sc.against_subsidy_component, 0)

			subsidy_component[sc.subsidy_component] += sc.amount_paid
			against_component[sc.against_subsidy_component] += sc.amount_paid
			
			self.loan_repayment_list.append(sc.name)

		for component, total_amount in subsidy_component.items():
			self.add_component_custom(component, "earnings", total_amount)

		for component, total_amount in against_component.items():
			self.add_component_custom(component, "deductions", total_amount)
		
	def add_loans_monthly_subsidy(self):
		if self.payroll_frequency != "Monthly":
			return
		
		monthly_subsidy = {}
		for l in self.loans:
			if not l.monthly_subsidy_component:
				continue

			monthly_subsidy.setdefault(l.monthly_subsidy_component, 0)
			diff = month_diff(self.end_date, l.repayment_start_date) - 1
			
			subsidy_amount = frappe.get_value('Monthly Subsidy', 
				{"from_month": ["<=", diff], "to_month": [">=", diff], "parent": l.loan},
				"subsidy_amount"
			) or 0

			monthly_subsidy[l.monthly_subsidy_component] += subsidy_amount

		for component, total_amount in monthly_subsidy.items():
			self.add_component_custom(component, "earnings", total_amount)

	def add_component_custom(self, component, component_type, total_amount, add_struck=None):
		struct_row = get_salary_component_data(component)
		struct_row.is_flexible_payment = 1

		if add_struck:
			struct_row.update(add_struck)

		self.update_component_row(
			struct_row, 
			flt(total_amount), 
			component_type,
			remove_if_zero_valued=True
		)

	def update_component_row(
		self,
		component_data,
		amount,
		component_type,
		additional_salary=None,
		is_recurring=0,
		data=None,
		default_amount=None,
		remove_if_zero_valued=None,
	):
		component_row = None
		for d in self.get(component_type):
			if d.salary_component != component_data.salary_component:
				continue

			if (not d.additional_salary and (not additional_salary or additional_salary.overwrite)) or (
				additional_salary and additional_salary.name == d.additional_salary
			):
				component_row = d
				break

		if additional_salary and additional_salary.overwrite:
			# Additional Salary with overwrite checked, remove default rows of same component
			self.set(
				component_type,
				[
					d
					for d in self.get(component_type)
					if d.salary_component != component_data.salary_component
					or (d.additional_salary and additional_salary.name != d.additional_salary)
					or d == component_row
				],
			)

		if not component_row:
			if not (amount or default_amount) and remove_if_zero_valued:
				return

			component_row = self.append(component_type)
			for attr in (
				"depends_on_payment_days",
				"salary_component",
				"abbr",
				"do_not_include_in_total",
				"is_tax_applicable",
				"is_flexible_benefit",
				"variable_based_on_taxable_salary",
				"exempted_from_income_tax",
				"is_flexible_payment",
				"against_employee_payment",
			):
				component_row.set(attr, component_data.get(attr))

		if additional_salary:
			if additional_salary.overwrite:
				component_row.additional_amount = flt(
					flt(amount) - flt(component_row.get("default_amount", 0)),
					component_row.precision("additional_amount"),
				)
			else:
				component_row.default_amount = 0
				component_row.additional_amount = amount

			component_row.is_recurring_additional_salary = is_recurring
			component_row.additional_salary = additional_salary.name
			component_row.deduct_full_tax_on_selected_payroll_date = (
				additional_salary.deduct_full_tax_on_selected_payroll_date
			)
		else:
			component_row.default_amount = default_amount or amount
			component_row.additional_amount = 0
			component_row.deduct_full_tax_on_selected_payroll_date = (
				component_data.deduct_full_tax_on_selected_payroll_date
			)

		component_row.amount = amount
		component_row.account_list_rate = component_data.get("account_rate") or "{}"

		self.update_component_amount_based_on_payment_days(component_row, remove_if_zero_valued)

		if data:
			data[component_row.abbr] = component_row.amount
			
	def get_data_for_eval(self):
		"""Returns data for evaluating formula"""
		data, default_data = super().get_data_for_eval()

		company = frappe.get_cached_doc("Company", self.company).as_dict()

		filters = { "company": self.company }
		data.natura_rate = default_data.natura_rate = frappe.get_value("Natura Price", {
			**filters, "valid_from": ["<=", self.end_date]}, "harga_beras", order_by="valid_from desc") or 0

		data.natura_multiplier = default_data.natura_multiplier = frappe.get_value("Natura Multiplier", {
			**filters, "pkp": data.pkp_status, "employment_type": data.employment_type }, "multiplier") or 0

		data.total_hari = default_data.total_hari = flt(frappe.get_value("Employment Type", data.employment_type, "hari_ump"))
		data.ump_harian = default_data.ump_harian = flt(company.ump_bulanan) / data.total_hari
		
		data.bpjs_amount = default_data.bpjs_amount = flt(company.ump_bulanan) \
			if data.custom_kriteria == "Satuan Hasil" else flt(data.ump_harian * data.payment_days)
		
		return data, default_data

@frappe.whitelist()
def debug_holiday():
	doc = frappe.get_doc("Salary Slip","Sal Slip/HR-EMP-00075/00001")
	doc.calculate_holidays()	

