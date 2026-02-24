import frappe
from datetime import date, timedelta

def create_employee_advance(self, method):
	company = frappe.get_doc("Company", self.company)
	account = frappe.get_doc("Account", company.default_receivable_account)
	employee = frappe.get_doc("Employee", self.employee)

	ea = frappe.new_doc("Employee Advance")
	ea.employee = self.employee
	ea.employee_name = self.employee_name
	ea.unit = employee.get("unit")
	ea.posting_date = self.custom_posting_date
	ea.company = self.company
	ea.purpose = self.purpose_of_travel
	ea.currency = account.account_currency
	ea.exchange_rate = 1
	ea.advance_amount = self.custom_grand_total_costing
	ea.advance_account = account.name
	ea.mode_of_payment = "Cash"

	ea.submit()
	self.db_set("custom_employee_advance", ea.name)

	# frappe.throw("custom create_employee_advance")
  
def cancel_employee_advance(self, method):
	ea = frappe.get_doc("Employee Advance", self.custom_employee_advance)
	ea.cancel()

	self.db_set("custom_employee_advance", "")
	# frappe.throw(self.custom_employee_advance)

def create_attendance(self,method):

	start_date = self.custom_estimate_depart_date
	end_date = self.custom_estimate_arrival_date

	if not start_date or not end_date:
		frappe.throw("Please set Estimate Depart and Arrival Date before submitting.")

	current_date = start_date
	while current_date <= end_date:
		if frappe.db.exists("Attendance", {
			"employee": self.employee,
			"attendance_date": current_date,
			"docstatus": ["!=", 2]
		}):
			frappe.msgprint(f"Attendance already exists for {current_date}, skipping.")
			current_date += timedelta(days=1)
			continue

		doc = frappe.new_doc("Attendance")
		doc.employee = self.employee
		doc.company = self.company
		doc.unit = self.unit
		doc.status = "On Leave"
		doc.leave_type = "Perjalanan Dinas"
		doc.attendance_date = current_date
		doc.submit()

		current_date += timedelta(days=1)


def debug():
	for row in frappe.db.sql(""" SELECT name FROM `tabTravel Request` WHERE docstatus = 1 """):
		create_attendance(frappe.get_doc("Travel Request",row[0]),"on_submit")
