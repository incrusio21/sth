# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import frappe
from sth.controllers.accounts_controller import AccountsController

class PertanggungjawabanPerjalananDinas(AccountsController):
	def validate(self):
		self.set_missing_value()
		super().validate()

	def on_submit(self):
		self.make_gl_entry()

	def on_cancel(self):
		super().on_cancel()
		self.make_gl_entry()

	def before_save(self):
		self.set_status_selisih()
	
	def set_status_selisih(self):
		tda = self.total_down_amount or 0
		tsa = self.total_sanctioned_amount or 0

		if tsa < tda:
			self.status_selisih = "Kurang Bayar"
		elif tsa > tda:
			self.status_selisih = "Lebih Bayar"
		else:
			self.status_selisih = "Tidak Ada Selisih"

		self.total_selisih = abs(tsa - tda)
		self.grand_total = self.total_selisih
		self.outstanding_amount = self.total_selisih

	@frappe.whitelist()
	def get_data_perjalanan_dinas(self):
		travel = frappe.get_doc("Travel Request", self.no_spd)
		emp_advance = frappe.get_doc("Employee Advance", travel.get("custom_employee_advance"))

		self.get_data_employee(travel)
		self.itinerary = travel.itinerary

		for costing in travel.costings:
			self.append("costings", {
				"expense_type": costing.expense_type,
				"keterangan": '',
				"amount": costing.total_amount,
				"sanctioned_amount": 0
			})

		self.total_down_amount = emp_advance.get("advance_amount", 0) if emp_advance else 0
  
	def get_data_employee(self, travel):
		employee = frappe.get_doc("Employee", travel.get("employee"))
		designation = frappe.get_doc("Designation", employee.designation)

		self.employee = employee.get("employee_name")
		self.nik = employee.get("name")
		self.grade = employee.get("grade")
		self.designation = designation.get("designation_name")
		self.department = employee.get("department")
		self.company = employee.get("company")