# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import frappe

class PertanggungjawabanPerjalananDinas(Document):
	@frappe.whitelist()
	def get_data_perjalanan_dinas(self):
		travel = frappe.get_doc("Travel Request", self.no_spd)

		self.get_data_employee(travel)
		self.itinerary = travel.itinerary

		for costing in travel.costings:
			self.append("costings", {
				"expense_type": costing.expense_type,
				"keterangan": '',
				"amount": costing.total_amount,
				"sanctioned_amount": 0
			})
  
	def get_data_employee(self, travel):
		employee = frappe.get_doc("Employee", travel.get("employee"))
		designation = frappe.get_doc("Designation", employee.designation)

		self.employee = employee.get("employee_name")
		self.nik = employee.get("name")
		self.grade = employee.get("grade")
		self.designation = designation.get("designation_name")
		self.department = employee.get("department")
		self.company = employee.get("company")