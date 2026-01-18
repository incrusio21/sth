# Copyright (c) 2026, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from hrms.hr.doctype.employee_transfer.employee_transfer import EmployeeTransfer
from sth.hr_customize.doctype.employee_update_log.employee_update_log import create_or_update_employee_propertry


class STHEmployeeTransfer(EmployeeTransfer):
	def before_submit(self):
		pass

	def on_submit(self):
		create_or_update_employee_propertry(self, self.transfer_date)
		# employee = frappe.get_doc("Employee", self.employee)
		# if self.create_new_employee_id:
		# 	new_employee = frappe.copy_doc(employee)
		# 	new_employee.name = None
		# 	new_employee.employee_number = None
		# 	new_employee = update_employee_work_history(
		# 		new_employee, self.transfer_details, date=self.transfer_date
		# 	)
		# 	if self.new_company and self.company != self.new_company:
		# 		new_employee.internal_work_history = []
		# 		new_employee.date_of_joining = self.transfer_date
		# 		new_employee.company = self.new_company
		# 	# move user_id to new employee before insert
		# 	if employee.user_id and not self.validate_user_in_details():
		# 		new_employee.user_id = employee.user_id
		# 		employee.db_set("user_id", "")
		# 	new_employee.insert()
		# 	self.db_set("new_employee_id", new_employee.name)
		# 	# relieve the old employee
		# 	employee.db_set("relieving_date", self.transfer_date)
		# 	employee.db_set("status", "Left")
		# else:
		# 	employee = update_employee_work_history(employee, self.transfer_details, date=self.transfer_date)
		# 	if self.new_company and self.company != self.new_company:
		# 		employee.company = self.new_company
		# 		employee.date_of_joining = self.transfer_date
		# 	employee.save()

	def on_cancel(self):
		for emp_log in frappe.get_all("Employee Update Log", filters={
			"voucher_type": self.doctype,
			"voucher_no": self.name
		}, pluck="name"):
			frappe.delete_doc("Employee Update Log", emp_log)
			
		# employee = frappe.get_doc("Employee", self.employee)
		# if self.create_new_employee_id:
		# 	if self.new_employee_id:
		# 		frappe.throw(
		# 			_("Please delete the Employee {0} to cancel this document").format(
		# 				f"<a href='/app/Form/Employee/{self.new_employee_id}'>{self.new_employee_id}</a>"
		# 			)
		# 		)
		# 	# mark the employee as active
		# 	employee.status = "Active"
		# 	employee.relieving_date = ""
		# else:
		# 	employee = update_employee_work_history(
		# 		employee, self.transfer_details, date=self.transfer_date, cancel=True
		# 	)
		# if self.new_company != self.company:
		# 	employee.company = self.company
		# employee.save()
	