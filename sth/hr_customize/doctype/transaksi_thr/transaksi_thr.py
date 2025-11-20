# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt, nowdate, today, date_diff, getdate

from sth.controllers.accounts_controller import AccountsController

class TransaksiTHR(AccountsController):
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
			"earning": hr_settings.earning_thr_component,
			"deduction": hr_settings.deduction_thr_component,
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
			"amount": flt(emp.subtotal),
			"salary_component": settings_field[log_type],
			"account": company.custom_default_thr_account
		})

		payment_log.insert(ignore_permissions=True)
		payment_log.submit()

		field_map = {
			"earning": "employee_payment_log_earning_thr",
			"deduction": "employee_payment_log_deduction_thr",
		}

		fieldname = field_map.get(log_type)
		if fieldname:
			frappe.db.set_value(
				"Detail Transaksi THR",
				emp.name,
				fieldname,
				payment_log.name
			)

	def remove_employee_payment_log(self, table_employee):
		for emp in table_employee:
			for field in ["employee_payment_log_earning_thr", "employee_payment_log_deduction_thr"]:
				frappe.db.set_value(
					"Detail Transaksi THR",
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
						frappe.log_error(f"Payment Log {log_name} tidak ditemukan", "Cancel Transaksi THR")

	@frappe.whitelist()
	def get_salary_structure_assignment(self, employee):
		return frappe.db.sql("""
			SELECT
			ssa.base as gaji_pokok
			FROM `tabSalary Structure Assignment` as ssa
			WHERE ssa.employee = %s
			ORDER BY ssa.from_date DESC
			LIMIT 1;
		""", (employee), as_dict=True)

	def get_jumlah_bulan_bekerja(self, date_of_joining):
		if not date_of_joining:
			return 0

		today_date = getdate(today())
		doj = getdate(date_of_joining)
		months = (today_date.year - doj.year) * 12 + (today_date.month - doj.month)
		return max(0, months)

	@frappe.whitelist()
	def get_all_employee(self, filters):
		records = frappe.get_list(
			"Employee",
			filters=filters,
			fields=[
			"no_ktp",
			"name",
			"pkp_status",
			"employee_name",
			"date_of_joining",
			"grade",
			"employment_type",
			"custom_kriteria",
			"bank_ac_no",
			"bank_name",
			"designation",
			"custom_divisi",
			"custom_kriteria",
			]
		)

		return records

	@frappe.whitelist()
	def get_thr_rate(self, employee, pkp_status=None, employee_grade=None, employment_type=None, kriteria=None):
		company = frappe.get_doc("Company", self.company)

		# ambil gaji pokok terbaru
		gaji_pokok = frappe.get_all(
			"Salary Structure Assignment",
			filters={"employee": employee},
			fields=["base"],
			order_by="from_date desc",
			limit=1
		)

		# ambil harga beras terbaru
		natura_price = frappe.get_all(
			"Natura Price",
			filters={"company": self.company},
			fields=["harga_beras"],
			order_by="valid_from desc",
			limit=1
		)

		# ambil multiplier berdasarkan pkp
		natura_multiplier = frappe.db.get_value(
			"Natura Multiplier",
			filters={"company": self.company, "pkp": pkp_status},
			fieldname="multiplier"
		)

		# ambil data date_of_joining
		date_of_joining = frappe.db.get_value("Employee", employee, "date_of_joining")
		days = date_diff(today(), getdate(date_of_joining))
		years = days / 365
		masa_kerja = "> 1 Tahun" if years > 1 else "< 1 Tahun"

		jumlah_bulan_bekerja = self.get_jumlah_bulan_bekerja(date_of_joining)

		thr_rule = self.get_thr_rule(employee_grade, employment_type, kriteria, masa_kerja)
		context = {
			"GP": gaji_pokok[0]["base"] if gaji_pokok else 0,
			"Natura": ((natura_price[0]["harga_beras"] if natura_price else 0) * (natura_multiplier or 0)),
			"Uang_Daging": company.custom_uang_daging or 0,
			"UMR": (company.custom_ump_harian or 0) * 30,
			"Jumlah_Bulan_Bekerja": jumlah_bulan_bekerja
    }
		subtotal = frappe.safe_eval(thr_rule or "0", None, context)

		return {
			"gaji_pokok": gaji_pokok[0]["base"] if gaji_pokok else 0,
			"umr": (company.custom_ump_harian or 0) * 30,
			"natura_price": natura_price[0]["harga_beras"] if natura_price else 0,
			"natura_multiplier": natura_multiplier or 0,
			"natura": ((natura_price[0]["harga_beras"] if natura_price else 0) * (natura_multiplier or 0)),
			"uang_daging": company.custom_uang_daging or 0,
			"masa_kerja": masa_kerja,
			"thr_rule": thr_rule,
			"jumlah_bulan_bekerja": jumlah_bulan_bekerja,
			"subtotal": subtotal
		}

	def get_thr_rule(self, employee_grade, employment_type=None, kriteria=None, masa_kerja=None):
		possible_filters = []

		if employment_type == "KHL" and masa_kerja:
			possible_filters.extend([
				{"employee_grade": employee_grade, "employment_type": employment_type, "kriteria": kriteria, "masa_kerja": masa_kerja},
				{"employee_grade": employee_grade, "employment_type": employment_type, "masa_kerja": masa_kerja},
				{"employee_grade": employee_grade, "kriteria": kriteria, "masa_kerja": masa_kerja},
				{"employee_grade": employee_grade, "masa_kerja": masa_kerja},
			])

		possible_filters.extend([
			{"employee_grade": employee_grade, "employment_type": employment_type, "kriteria": kriteria},
			{"employee_grade": employee_grade, "employment_type": employment_type},
			{"employee_grade": employee_grade, "kriteria": kriteria},
			{"employee_grade": employee_grade},
		])

		for f in possible_filters:
			thr_rule = frappe.db.get_value("THR Setup Rule", f, "formula")
			if thr_rule:
					return thr_rule

		return None
	
@frappe.whitelist()
def get_payment_entry(dt, dn, party_amount=None, bank_account=None, bank_amount=None):
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
	payment_settings = frappe.get_single("Payment Settings")

	# paid_amount, received_amount = get_paid_amount_and_received_amount(
	# 	doc, party_account_currency, bank, outstanding_amount, payment_type, bank_amount
	# )

	pe = frappe.new_doc("Payment Entry")
	pe.payment_type = payment_type
	pe.company = doc.company
	pe.posting_date = nowdate()
	pe.party_type = "Employee"
	pe.internal_employee = 1
	pe.party = payment_settings.internal_employee
	pe.party_name = payment_settings.internal_employee
	pe.bank_account = bank_account.name
	pe.paid_from = bank_account.account
	pe.paid_to = company.default_payable_account
	pe.paid_amount = doc.grand_total
	pe.received_amount = doc.grand_total
	pe.total_allocated_amount = doc.grand_total

	pe.append(
		"references",
		{
			"reference_doctype": dt,
			"reference_name": dn,
			"total_amount": doc.grand_total,
			"outstanding_amount": doc.grand_total,
			"allocated_amount": doc.grand_total,
		},
	)

	pe.setup_party_account_field()
	pe.set_missing_values()
	pe.set_missing_ref_details()

	return pe