import frappe

@frappe.whitelist()
def approve_api(self,method):
	if self.owner != "api@sth.com":
		return

	# hook terpasang untuk semua doctype, lewati yang tidak submittable
	# (Employee Payment Log, Buku Kerja Mandor Premi, dll yang dibuat saat on_submit)
	if not self.meta.is_submittable or self.docstatus != 0:
		return

	self.submit()