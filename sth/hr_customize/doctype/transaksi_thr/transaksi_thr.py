# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, nowdate, today, date_diff, getdate

class TransaksiTHR(Document):
	def on_submit(self):
		# self.create_journal_entry()
		for emp in self.table_employee:
			self.make_employee_payment_log(emp, "earning")
			self.make_employee_payment_log(emp, "deduction")

	def on_cancel(self):
		self.delete_journal_entry()
		self.remove_employee_payment_log(self.table_employee)

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

	def create_journal_entry(self):
		company = frappe.get_doc("Company", self.company)

		total_thr = sum(emp.subtotal for emp in self.table_employee if emp.subtotal)

		je = frappe.new_doc("Journal Entry")
		je.update({
			"company": self.company,
			"posting_date": self.posting_date,
		})

		# Buat kedua baris akun
		debit_row = {
			"account": self.payable_thr_account,
			"debit_in_account_currency": total_thr
		}

		credit_row = {
			"account": self.thr_account,
			"credit_in_account_currency": total_thr
		}

		debit_row["against_account"] = self.thr_account
		credit_row["against_account"] = self.payable_thr_account

		je.append("accounts", debit_row)
		je.append("accounts", credit_row)

		je.set_total_debit_credit()
		je.submit()

		self.db_set("journal_entry", je.name)

	def delete_journal_entry(self):
		if self.journal_entry:
			je_name = self.journal_entry

			try:
				je = frappe.get_doc("Journal Entry", je_name)
				
				if je.docstatus == 1:
						je.cancel()
				
				frappe.delete_doc("Journal Entry", je_name, force=1)
				self.db_set("journal_entry", None)

			except frappe.DoesNotExistError:
				frappe.msgprint(f"Journal Entry {je_name} tidak ditemukan, mungkin sudah dihapus.")
			except Exception as e:
				frappe.throw(f"Gagal menghapus Journal Entry {je_name}: {str(e)}")

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
	def get_thr_rate(self, employee, pkp_status, employee_grade, employment_type, kriteria):
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