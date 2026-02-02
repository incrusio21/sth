# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt, get_link_to_form

from sth.controllers.accounts_controller import AccountsController

class EmployeePotongan(AccountsController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._expense_account = "expense_account"

	def validate(self):
		self.set_missing_value()
		self.check_employee_status()

	def calculate_total(self):
		totals = 0
		for d in self.details:
			totals += flt(d.rate)
		
		self.grand_total = flt(totals, self.precision("grand_total"))
		
	def check_employee_status(self):
		emp_list = [d.employee for d in self.details]

		emp = frappe.qb.DocType("Employee")
		error_emp = (
			frappe.qb.from_(emp)
			.select(
				emp.name, emp.employee_name
			)
			.where(
				(emp.name.isin(emp_list)) & 
				( 
					(emp.status != "Active") | (emp.grade != self.employee_grade)
	 			)
			)
		).run(as_dict=1)
		
		err_message = ""
		for err in error_emp:
			if not err_message:
				err_message = "There is an employee who does not meet the standard:" 
			err_message += "<br>" + get_link_to_form("Employee", err.name, err.employee_name)

		if err_message:
			frappe.throw(err_message, title="Does't meet the Standard")

	def on_submit(self):
		self.create_additional_salary()
		self.make_gl_entry()

	def create_additional_salary(self):
		for d in self.details:
			add_sal = frappe.new_doc("Additional Salary")
			add_sal.company = self.company
			add_sal.employee = d.employee
			add_sal.payroll_date = self.posting_date
			add_sal.salary_component = self.salary_component
			add_sal.amount = d.rate
			add_sal.overwrite_salary_structure_amount = 1

			add_sal.submit()

			d.db_set("additional_salary", add_sal.name)

	def on_cancel(self):
		super().on_cancel()

		self.remove_additional_salary()
		self.make_gl_entry()
	
	def remove_additional_salary(self):
		for d in self.get("details", {"additional_salary": True}):
			doc = frappe.get_doc("Additional Salary", d.additional_salary)
			if doc.docstatus == 1:
				doc.cancel()

			doc.delete(force=True)

			d.db_set("additional_salary", "")
		
	@frappe.whitelist()
	def get_employee(self):
		jenis_potongan = frappe.get_value("Jenis Potongan", self.jenis_potongan ,'default_rate')
		# emp_list = frappe.get_all("Employee", filters={"status": "Active", "employment_type": self.employment_type}, fields=["name", "employee_name"])
		emp_list = frappe.db.sql("""
			SELECT 
			e.name,
			e.employee_name
			FROM `tabEmployee` as e
			JOIN `tabEmployee Jenis Potongan` as ejp ON ejp.parent = e.name
			WHERE e.status = 'Active' AND e.grade = %(grade)s AND ejp.jenis_potongan = %(jenis_potongan)s;
    """, {"grade": self.employee_grade, "jenis_potongan": self.jenis_potongan}, as_dict=True)

		self.details = []
		for d in emp_list:
			self.append("details", {
				"employee": d.name,
				"employee_name": d.employee_name,
				"rate": jenis_potongan
			})

@frappe.whitelist()
def fetch_company_account(company):
	accounts_dict = {
		"credit_to": frappe.get_cached_value("Company", company, "pengajuan_pembayaran_account"),
	}

	return accounts_dict