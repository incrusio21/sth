import frappe

def check_persetujuan(self, method):
	if not self.is_new():
		old_doc = self.get_doc_before_save()
		old_state = old_doc.get("workflow_state") if old_doc else None
		new_state = self.get("workflow_state")
			
		if self.get("persetujuan_1"):
			if "Persetujuan 1" in old_state and old_state != new_state:
				if frappe.session.user != self.get("persetujuan_1"):
					frappe.throw("User {} yang hanya boleh approve ketika butuh Persetujuan 1".format(self.get("persetujuan_1")))

		if self.get("persetujuan_2"):
			if "Persetujuan 2" in old_state and old_state != new_state:
				if frappe.session.user != self.get("persetujuan_2"):
					frappe.throw("User {} yang hanya boleh approve ketika butuh Persetujuan 2".format(self.get("persetujuan_2")))

	if self.status == "Non Aktif":
		self.disabled = 1
	else:
		self.disabled = 0

def cek_status_awal(doc, method):
	if doc.status == "Aktif":
		doc.workflow_state = "Approved"
		frappe.db.set_value('Item', doc.name, 'workflow_state', 'Approved', update_modified=False)
	else:
		frappe.db.set_value('Item', doc.name, 'workflow_state', 'Butuh Persetujuan 1', update_modified=False)