import frappe
def isi_golongan(self,method):
	doctype = {"Employee Grievance" : "grievance_against"}

	if self.doctype == "Employee Grievance":
		self.golongan_employee = frappe.get_doc("Employee", self.get("grievance_against")).grade
