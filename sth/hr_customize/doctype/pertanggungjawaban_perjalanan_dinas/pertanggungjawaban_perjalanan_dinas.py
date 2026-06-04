# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import frappe
from frappe.model.mapper import get_mapped_doc
from sth.controllers.accounts_controller import AccountsController
from frappe import _
class PertanggungjawabanPerjalananDinas(AccountsController):
	def validate(self):
		# self.set_missing_value()
		super().validate()

	def on_submit(self):
		if self.status_selisih != "Tidak Ada Selisih":
			self.make_gl_entries()

	def on_cancel(self):
		super().on_cancel()
		if self.status_selisih != "Tidak Ada Selisih":
			self.cancel_gl_entries()

	def make_gl_entries(doc, method=None):

		gl_entries = []
		akun_debit = ""
		total_debit = 0
		for row in doc.costings:
			expense_type_doc = frappe.get_doc("Expense Claim Type",row.expense_type)
			for et_baris in expense_type_doc.accounts:
				if et_baris.company == doc.company:
					akun_debit = et_baris.default_account

			# --- DEBIT ---
			gl_entries.append(
				frappe.get_doc({
					"doctype": "GL Entry",
					"posting_date": doc.posting_date,
					"account": akun_debit,
					"debit": row.sanctioned_amount,
					"credit": 0.0,
					"debit_in_account_currency": row.sanctioned_amount,
					"credit_in_account_currency": 0.0,
					"voucher_type": doc.doctype,
					"voucher_no": doc.name,
					"company": doc.company,
					"remarks": f"Pertanggungjawaban Perjalanan Dinas - {row.expense_type} - {doc.name}",
					"cost_center": frappe.get_doc("Company", doc.company).cost_center
				})
			)

			total_debit += row.sanctioned_amount

		uang_muka = 0
		if doc.total_down_amount:
			uang_muka = doc.total_down_amount

			# --- CREDIT ---
			gl_entries.append(
				frappe.get_doc({
					"doctype": "GL Entry",
					"posting_date": doc.posting_date,
					"account": doc.advance_account,
					"debit": 0.0,
					"credit": uang_muka,
					"debit_in_account_currency": 0.0,
					"credit_in_account_currency": uang_muka,
					"voucher_type": doc.doctype,
					"voucher_no": doc.name,
					"company": doc.company,
					"remarks": f"Pertanggungjawaban Perjalanan Dinas - {doc.name}",
					"is_opening": "No",
					"cost_center": frappe.get_doc("Company", doc.company).cost_center
				})
			)

		sisa = total_debit - uang_muka
		# --- CREDIT ---
		gl_entries.append(
			frappe.get_doc({
				"doctype": "GL Entry",
				"posting_date": doc.posting_date,
				"account": doc.credit_to,
				"debit": 0.0,
				"credit": sisa,
				"debit_in_account_currency": 0.0,
				"credit_in_account_currency": sisa,
				"voucher_type": doc.doctype,
				"voucher_no": doc.name,
				"company": doc.company,
				"remarks": f"Pertanggungjawaban Perjalanan Dinas - {doc.name}",
				"is_opening": "No",
				"cost_center": frappe.get_doc("Company", doc.company).cost_center,
				"party_type": "Employee",
				"party": doc.employee
			})
		)

		# Simpan semua GL Entry
		for gl in gl_entries:
			gl.flags.ignore_permissions = True
			gl.insert()

		frappe.msgprint(_("GL Entry berhasil dibuat."), indicator="green", alert=True)

	def cancel_gl_entries(doc, method=None):
		"""
		Batalkan (reverse) GL Entry saat dokumen di-cancel.
		"""
		frappe.db.sql(
			"""
			UPDATE `tabGL Entry`
			SET is_cancelled = 1
			WHERE voucher_type = %s
			  AND voucher_no   = %s
			  AND is_cancelled = 0
			""",
			(doc.doctype, doc.name),
		)
		frappe.msgprint(_("GL Entry berhasil dibatalkan."), indicator="orange", alert=True)

	def before_save(self):
		self.set_status_selisih()
	
	def set_status_selisih(self):
		tda = self.total_down_amount or 0
		tsa = self.total_sanctioned_amount or 0

		if tsa < tda:
			self.status_selisih = "Lebih Bayar"
		elif tsa > tda:
			self.status_selisih = "Kurang Bayar"
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
		self.advance_account = emp_advance.get("advance_account")
  
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
		target.no_rekening = employee.bank_ac_no
		target.nama_bank = employee.nama_bank
		target.unit = employee.unit
		target.no_rekening_tujuan = employee.bank_ac_no
		target.bank_tujuan = employee.bank_name
		target.paid_amount = source.outstanding_amount
		target.paid_from_account_currency = "IDR"
		target.paid_to_account_currency = "IDR"
		target.received_amount = source.outstanding_amount
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
					"credit_to": "paid_to",
				}
			}
		},
		target_doc,
		post_process,
	)
 
	return doclist