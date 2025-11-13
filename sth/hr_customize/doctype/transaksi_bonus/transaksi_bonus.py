# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt, nowdate

from sth.controllers.accounts_controller import AccountsController

class TransaksiBonus(AccountsController):
	
	def validate(self):
		self.calculate()
		self.set_missing_value()
		super().validate()

	def calculate(self):
		grand_total = 0
		for row in self.table_employee:
			grand_total += row.subtotal

		self.grand_total = flt(grand_total)

	def on_submit(self):
		for emp in self.table_employee:
			self.make_employee_payment_log(emp, "earning")
			self.make_employee_payment_log(emp, "deduction")

		self.make_gl_entry()

	def on_cancel(self):
		super().on_cancel()
		self.remove_employee_payment_log(self.table_employee)
		self.make_gl_entry()
		
	def make_employee_payment_log(self, emp, log_type):
		hr_settings = frappe.get_single("Bonus and Allowance Settings")
		company = frappe.get_doc("Company", self.company)

		settings_field = {
			"earning": hr_settings.earning_bonus_component,
			"deduction": hr_settings.deduction_bonus_component,
		}

		if not settings_field.get(log_type):
			frappe.throw(f"Salary Component untuk '{log_type}' belum diset di Bonus and Allowance Settings")

		payment_log = frappe.new_doc("Employee Payment Log")
		payment_log.update({
			"employee": emp.employee,
			"hari_kerja": 1,
			"company": self.company,
			"posting_date": self.posting_date,
			"payroll_date": self.posting_date,
			"status": "Approved",
			"is_paid": 0,
			"amount": flt(emp.total_bonus),
			"salary_component": settings_field[log_type],
			"account": company.custom_default_bonus_account
		})

		payment_log.insert(ignore_permissions=True)
		payment_log.submit()

		field_map = {
			"earning": "employee_payment_log_earning_bonus",
			"deduction": "employee_payment_log_deduction_bonus",
		}

		fieldname = field_map.get(log_type)
		if fieldname:
			frappe.db.set_value(
				"Detail Transaksi Bonus",
				emp.name,
				fieldname,
				payment_log.name
			)

	def remove_employee_payment_log(self, table_employee):
		for emp in table_employee:
			for field in ["employee_payment_log_earning_bonus", "employee_payment_log_deduction_bonus"]:
				frappe.db.set_value(
					"Detail Transaksi Bonus",
					emp.name,
					field,
					None
				)
				log_name = emp.get(field)
				if log_name:
					try:
						log_doc = frappe.get_doc("Employee Payment Log", log_name)
						if log_doc.docstatus == 1:
							log_doc.cancel()
						log_doc.delete(ignore_permissions=True)
					except frappe.DoesNotExistError:
						frappe.log_error(f"Payment Log {log_name} tidak ditemukan", "Cancel Transaksi Bonus")

	@frappe.whitelist()
	def get_setup_bonus(self, name, kpi_value):
		return frappe.db.sql("""
			SELECT
			sb.name,
			dpb.kv as kpi_value,
			dpb.cv as compensation_value
			FROM `tabSetup Bonus` as sb
			JOIN `tabDetail Parameter Bonus` as dpb ON dpb.parent = sb.name
			WHERE sb.name = %s AND dpb.kv = %s;
		""", (name, kpi_value), as_dict=True)

	@frappe.whitelist()
	def calculate_total_bonus(self, company, kriteria, employee, name, kpi_value):
		salary = 0
		setup_bonus = frappe.db.sql("""
			SELECT
			sb.name,
			dpb.kv as kpi_value,
			dpb.cv as compensation_value
			FROM `tabSetup Bonus` as sb
			JOIN `tabDetail Parameter Bonus` as dpb ON dpb.parent = sb.name
			WHERE sb.name = %s AND dpb.kv = %s;
		""", (name, kpi_value), as_dict=True)

		if kriteria == "Satuan Hasil":
			company = frappe.get_doc("Company", company)
			salary = flt(company.custom_ump_harian * 30)
		elif kriteria == "Non Satuan Hasil":
			latest_ssa = frappe.db.get_value(
				"Salary Structure Assignment",
				{"employee": employee},
				["name", "base"],
				order_by="from_date desc",
				as_dict=True
			)
			salary = flt(latest_ssa.base) if latest_ssa else 0

		return {
			"setup_bonus": {
				"name": setup_bonus[0].name,
				"kpi_value": setup_bonus[0].kpi_value,
				"compensation_value": setup_bonus[0].compensation_value,
			},
			"bonus": {
				"salary": salary,
			}
		}

@frappe.whitelist()
def get_payment_entry_for_training_event(dt, dn, party_amount=None, bank_account=None, bank_amount=None):
	doc = frappe.get_doc(dt, dn)

	# party_account = get_party_account(doc)
	# party_account_currency = get_account_currency(party_account)
	payment_type = "Pay"
	# grand_total, outstanding_amount = get_grand_total_and_outstanding_amount(
	# 	doc, party_amount, party_account_currency
	# )

	# # bank or cash
	# bank = get_bank_cash_account(doc, bank_account)
	bank_account = frappe.get_doc("Bank Account", {"company": doc.company})
	company = frappe.get_doc("Company", doc.company)

	# paid_amount, received_amount = get_paid_amount_and_received_amount(
	# 	doc, party_account_currency, bank, outstanding_amount, payment_type, bank_amount
	# )

	pe = frappe.new_doc("Payment Entry")
	pe.payment_type = payment_type
	pe.company = doc.company
	pe.posting_date = nowdate()
	pe.party_type = "Employee"
	pe.party = "SADIMIN"
	# pe.party_name = frappe.get_doc("Supplier", doc.get("supplier")).supplier_name
	# pe.bank_account = bank_account.name
	# pe.paid_from = bank_account.account
	# pe.paid_to = company.default_payable_account
	# pe.paid_amount = doc.custom_grand_total_costing
	# pe.received_amount = doc.custom_grand_total_costing

	# pe.append(
	# 	"references",
	# 	{
	# 		"reference_doctype": dt,
	# 		"reference_name": dn,
	# 		"total_amount": doc.custom_grand_total_costing,
	# 		"outstanding_amount": doc.custom_grand_total_costing,
	# 		"allocated_amount": doc.custom_grand_total_costing,
	# 	},
	# )

	# pe.setup_party_account_field()
	# pe.set_missing_values()
	# pe.set_missing_ref_details()

	return pe