import frappe

def autoname_employee(self,method):
	self.finger_id = self.no_ktp[:14]
	self.name = self.no_ktp