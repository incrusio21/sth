import frappe

@frappe.whitelist()
def approve_api(self,method):
	if self.owner == "api@sth.com":
		self.submit()