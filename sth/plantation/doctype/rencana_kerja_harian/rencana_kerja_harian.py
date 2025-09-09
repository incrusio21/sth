# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class RencanaKerjaHarian(Document):
	def validate(self):
		self.validate_duplicate_rkh()
		self.check_material()
	
	def duplicate_rkh(self):
		pass

	def check_material(self):
		if self.tipe_kegiatan != "Perawatan":
			self.material = []

	def on_submit(self):
		self.update_rkb_used()

	def on_cancel(self):
		self.update_rkb_used()

	def update_rkb_used(self):
		frappe.get_doc(self.rkb_type, self.rkb_no).update_used_total()

@frappe.whitelist()
def get_rencana_kerja_bulanan(kode_kegiatan, tipe_kegiatan, divisi, blok, tanggal_rkh):
	voucher_type = frappe.get_value("Tipe Kegiatan", tipe_kegiatan, "rkb_voucher_type")
	rkb = frappe.db.get_value(voucher_type, {
		"kode_kegiatan": kode_kegiatan, "divisi": divisi, "blok": blok, "from_date": [">=", tanggal_rkh], "to_date": ["<=", tanggal_rkh],
		"docstatus": 1
	})

	if not rkb:
		frappe.throw(""" Rencana Kerja Bulanan not Found for <br> 
			Kegiatan : {} <br> 
			Divisi : {} <br> 
			Blok : {} <br>
			Date : {} """.format(kode_kegiatan, divisi, blok, tanggal_rkh))

	# no rencana kerja bualanan
	ress = { "rkb_type": voucher_type, "rkb_no": rkb}
	if voucher_type == "Rencana Kerja Bulanan Perawatan":
		ress["material"] = frappe.db.get_all("Detail Material RK", 
			filters={"parent": rkb}, fields=["item", "uom", "name as prevdoc_detail"]
		)

	return ress


