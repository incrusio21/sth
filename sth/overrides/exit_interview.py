import frappe

from frappe.model.mapper import get_mapped_doc
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
			"name": self.name
		}
		query = """ SELECT * FROM `tabExit Interview` 
				WHERE employee = %(employee)s AND ref_doctype = %(ref_doctype)s AND reference_document_name IS NULL AND name <> %(name)s"""
		exit = frappe.db.sql(query, cond, as_dict=True)
		if exit and len(exit) > 0:
			frappe.throw(f"Dokumen Exit Interview dengan Employee <b>{self.employee} : {self.employee_name}</b> masih ada yang belum digunakan")
   

@frappe.whitelist()
def make_perhitungan_kompensasi_phk(source_name, target_doc=None):
    doc = get_mapped_doc(
		"Exit Interview",
		source_name,
		{
			"Exit Interview": {
				"doctype": "Perhitungan Kompensasi PHK",
				"field_map": {
					"relieving_date": "l_date",
					"name": "exit_interview",
					"date": "posting_date",
					"custom_upload_file_document": "exit_interview_attach"
				}
			}
		}
	)
    
    
    return doc