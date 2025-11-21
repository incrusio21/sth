import frappe

from hrms.hr.doctype.exit_interview.exit_interview import ExitInterview

class ExitInterview(ExitInterview):
	def validate(self):
		super().validate_relieving_date()
		super().set_employee_email()
		self.check_exit_interview_not_used()
	def check_exit_interview_not_used(self):
		cond = {
			"employee": self.employee,
			"ref_doctype": "Perhitungan Kompensasi PHK",
		}
		query = """ SELECT * FROM `tabExit Interview` WHERE employee = %(employee)s AND ref_doctype = %(ref_doctype)s AND reference_document_name IS NULL """
		exit = frappe.db.sql(query, cond, as_dict=True)
		if exit and len(exit) > 0:
			frappe.throw(f"Dokumen Exit Interview dengan Employee <b>{self.employee} : {self.employee_name}</b> masih ada yang belum digunakan")