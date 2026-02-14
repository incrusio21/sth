# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import frappe
from frappe.model.mapper import get_mapped_doc
from sth.controllers.accounts_controller import AccountsController

class PertanggungjawabanPerjalananDinas(AccountsController):
	def validate(self):
		# self.set_missing_value()
		super().validate()

	def on_submit(self):
		if self.status_selisih != "Tidak Ada Selisih":
			self.make_gl_entry()

	def on_cancel(self):
		super().on_cancel()
		if self.status_selisih != "Tidak Ada Selisih":
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

		if travel.tf == "Guest":
			self.guests = travel.table_dcyg

		self.get_data_employee(travel)
		self.itinerary = travel.itinerary

		# reset child table dulu
		self.costings = []

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

		self.travel_for = travel.get("tf")
		self.employee = employee.get("name")
		self.employee = employee.get("name")
		self.nik = employee.get("name")
		self.grade = employee.get("grade")
		self.designation = designation.get("designation_name")
		self.department = employee.get("department")
		self.company = employee.get("company")
  
@frappe.whitelist()
def make_payment_entry(source_name, target_doc=None):
	def post_process(source, target):
		employee = frappe.db.get_value("Employee", source.employee, "*")
		company = frappe.db.get_value("Company", source.company, "*")

		if source.status_selisih == "Lebih Bayar":
			target.payment_type = "Receive"
		elif source.status_selisih == "Kurang Bayar":
			target.payment_type = "Pay"
    
		target.party_type = "Employee"
		target.party = employee.name
		target.party_name = employee.employee_name
		target.unit = employee.unit
		target.paid_amount = source.outstanding_amount
		target.paid_from_account_currency = "IDR"
		target.paid_to_account_currency = "IDR"
		target.append("references", {
			"reference_doctype": "Pertanggungjawaban Perjalanan Dinas",
			"reference_name": source.name,
			"total_amount": source.grand_total,
			"outstanding_amount": source.outstanding_amount,
			"allocated_amount": source.outstanding_amount
		})
	doclist = get_mapped_doc(
		"Pertanggungjawaban Perjalanan Dinas",
		source_name,
		{
			"Pertanggungjawaban Perjalanan Dinas": {
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