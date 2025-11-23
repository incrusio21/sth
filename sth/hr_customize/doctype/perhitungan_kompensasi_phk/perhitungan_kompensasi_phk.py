# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
import calendar

from frappe.utils import month_diff, getdate
from frappe.model.mapper import get_mapped_doc

from hrms.hr.doctype.leave_application.leave_application import get_leave_balance_on
from sth.controllers.accounts_controller import AccountsController

class PerhitunganKompensasiPHK(AccountsController):
	def on_submit(self):
		self.make_gl_entry()
		self.update_exit_interview()

	def on_cancel(self):
		super().on_cancel()
		self.make_gl_entry()

	@frappe.whitelist()
	def fetch_perhitungan(self):
		employee = frappe.db.get_value("Employee", self.employee, "*")
		working_month = month_diff(self.l_date, employee.date_of_joining)
		self.table_seym = []
		grand_total = 0
		base = 0
		if employee.grade == "NON STAF" and employee.custom_kriteria == "Satuan Hasil":
			ump_harian = frappe.db.get_value("Company", self.company, "custom_ump_harian")
			l_date = getdate(self.l_date)
			days_in_month = calendar.monthrange(l_date.year, l_date.month)[1]
			base = ump_harian * days_in_month
		else:
			base = frappe.db.get_value("Salary Structure Assignment", self.ssa, "base")
			
		setup_dasar_phk_components = frappe.db.get_all("Detail Dasar PHK", {"parent": self.dphk}, "*")

		for row in setup_dasar_phk_components:
			query = """ SELECT * FROM `tabSetup Komponen PHK` WHERE name = %(name)s AND (employee_grade = %(grade)s OR employee_grade is NULL) LIMIT 1"""
			values = {
				"name": row.nm,
				"grade": self.eg
			}
			setup_komponen_phk = frappe.db.sql(query, values, as_dict=True)
			setup_komponen_company = frappe.db.get_value("Setup Komponen Company", {'parent': row.nm, 'company': self.company}, "*")
			if not setup_komponen_phk or not setup_komponen_company:
				continue

			perhitungan_component = {
				"nm": row.nm,
				"fp": row.fp if row and row.fp else 0,
				"gaji_pokok": base
			}
			cond = {
				"parent": row.nm,
				"from_month": ['<=', working_month],
				"to_month": ['>=', working_month],
			}
			detail_setup_komponen = frappe.db.get_value("Detail Setup Komponen PHK", cond, "*")

			perhitungan_component.update({"fps": (detail_setup_komponen.pengkali if detail_setup_komponen and detail_setup_komponen.pengkali else 0)})
			result = perhitungan_component["fp"] * perhitungan_component["fps"] * base
			if setup_komponen_phk[0].is_cuti:
				remaining_leave = get_cuti_balance(setup_komponen_phk[0].tipe_cuti, self.l_date, self.employee)
				result = remaining_leave / 30 * base
			if detail_setup_komponen and detail_setup_komponen.maximum > 0  and result > detail_setup_komponen.maximum:
				result = detail_setup_komponen.maximum
			grand_total += result
			perhitungan_component.update({"sbttl": result})
			self.append("table_seym", perhitungan_component)

		self.grand_total = grand_total
		self.outstanding_amount = grand_total


	def update_exit_interview(self):
		updated = {
			"reference_document_name": self.name
		}
		frappe.db.set_value("Exit Interview", self.exit_interview, updated)

	@frappe.whitelist()
	def fetch_ssa(self):
		employee = frappe.db.get_value("Employee", self.employee, "*")
		if employee.grade == "NON STAF" and employee.custom_kriteria == "Satuan Hasil":
			return
		ssa = frappe.db.get_all('Salary Structure Assignment', filters={'employee': self.employee}, order_by='from_date desc', page_length=1)
		if not ssa:
			frappe.throw(f"Salary Structure Assignment <b> {self.employee} : {self.employee_name}</b>")
		self.ssa = ssa[0].name
  
	@frappe.whitelist()
	def fetch_default_account(self):
		company = frappe.db.get_value("Company", self.company, "*")
		self.salary_account = company.custom_default_phk_salary_account
		self.credit_to = company.custom_default_phk_account

	@frappe.whitelist()
	def fetch_default_salary_component(self):
		earning_phk = frappe.db.get_single_value("Bonus and Allowance Settings", "earning_phk_component")
		deduction_phk = frappe.db.get_single_value("Bonus and Allowance Settings", "deduction_phk_component")
		self.earning_phk_component = earning_phk
		self.deduction_phk_component = deduction_phk

def get_cuti_balance(leave_type, date, employee):
	result = get_leave_balance_on(employee, leave_type, date)
	return result

@frappe.whitelist()
def filter_exit_interview(doctype, txt, searchfield, start, page_len, filters):
	cond = {
			"employee": filters.get("employee"),
			"ref_doctype": "Perhitungan Kompensasi PHK",
		}
	query = """ SELECT name AS value FROM `tabExit Interview` 
		WHERE employee = %(employee)s AND ref_doctype = %(ref_doctype)s 
		AND reference_document_name IS NULL"""
	result = frappe.db.sql(query, cond)

	return result

@frappe.whitelist()
def make_payment_entry(source_name, target_doc=None):
	def post_process(source, target):
		internal_employee = frappe.db.get_single_value("Payment Settings", "internal_employee")
		employee = frappe.db.get_value("Employee", internal_employee, "*")
		company = frappe.db.get_value("Company", source.company, "*")
  
		target.internal_employee = 1
		target.payment_type = "Pay"
		target.party_type = "Employee"
		target.party = employee.name
		target.party_name = employee.employee_name
		target.paid_amount = source.outstanding_amount
		target.paid_to_account_currency = company.default_currency
		target.append("references", {
			"reference_doctype": "Perhitungan Kompensasi PHK",
			"reference_name": source.name,
			"total_amount": source.grand_total,
			"outstanding_amount": source.outstanding_amount,
			"allocated_amount": source.outstanding_amount
		})
	doclist = get_mapped_doc(
		"Perhitungan Kompensasi PHK",
		source_name,
		{
			"Perhitungan Kompensasi PHK": {
				"doctype": "Payment Entry",
				"field_map": {
					"salary_account": "paid_from",
					"credit_to": "paid_to"
				}
			}
		},
  		target_doc,
		post_process,
	)
 
	return doclist	