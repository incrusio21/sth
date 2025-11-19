# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
import calendar

from frappe.utils import month_diff, getdate

from hrms.hr.doctype.leave_application.leave_application import get_leave_balance_on
from sth.controllers.accounts_controller import AccountsController

class PerhitunganKompensasiPHK(AccountsController):
	def on_submit(self):
		self.make_gl_entry()

	def on_cancel(self):
		super().on_cancel()
		self.make_gl_entry()

	@frappe.whitelist()
	def fetch_perhitungan(self):
		employee = frappe.db.get_value("Employee", self.employee, "*")
		base = 0
		if employee.grade == "NON STAF" and employee.custom_kriteria == "Satuan Hasil":
			ump_harian = frappe.db.get_value("Company", self.company, "custom_ump_harian")
			l_date = getdate(self.l_date)
			days_in_month = calendar.monthrange(l_date.year, l_date.month)[1]
			base = ump_harian * days_in_month
		else:
			base = frappe.db.get_value("Salary Structure Assignment", self.ssa, "base")
		setup_dasar_phk_components = frappe.db.get_all("Detail Dasar PHK", {"parent": self.dphk}, "*")

		working_month = month_diff(self.l_date, employee.date_of_joining)
		for row in setup_dasar_phk_components:
			setup_komponen_phk = frappe.db.get_value("Setup Komponen PHK", {'name': row.nm, 'employee_grade': self.eg}, "*")
			setup_komponen_company = frappe.db.get_value("Setup Komponen Company", {'parent': row.nm, 'company': self.company}, "*")
			if not setup_komponen_phk or not setup_komponen_company:
				continue

			perhitungan_component = {
				"nm": row.nm,
				"fp": row.fp,
				"gaji_pokok": base
			}
			cond = {
				"parent": row.nm,
				"from_month": ['<', working_month],
				"to_month": ['>', working_month],
			}
			pengkali_komponen = frappe.db.get_value("Detail Setup Komponen PHK", cond, "pengkali")

			perhitungan_component.update({"fps": (pengkali_komponen if pengkali_komponen else 0)})
			result = row.fp * perhitungan_component["fps"] * base
			if setup_komponen_phk.is_cuti:
				remaining_leave = get_cuti_balance(setup_komponen_phk.tipe_cuti, self.l_date, self.employee)
				result = remaining_leave / 30 * base
			perhitungan_component.update({"sbttl": result})
			self.append("table_seym", perhitungan_component)


	@frappe.whitelist()
	def fetch_ssa(self):
		ssa = frappe.db.get_all('Salary Structure Assignment', filters={'employee': self.employee}, order_by='from_date desc', page_length=1)
		employee = frappe.db.get_value("Employee", self.employee, "*")
		if employee.grade != "NON STAF" and employee.custom_kriteria != "Satuan Hasil":
			if not ssa:
				frappe.throw(f"Salary Structure Assignment <b> {self.employee} : {self.employee_name}</b>")
			self.ssa = ssa[0].name

def get_cuti_balance(leave_type, date, employee):
	result = get_leave_balance_on(employee, leave_type, date)
	return result