# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class DaftarMasyarakat(Document):
	def on_update(self):
		if self.has_value_changed("pd"):
			self.update_gis_perangkat_desa()

	def update_gis_perangkat_desa(self):
		frappe.msgprint(
			"Mengubah Semua GIS yang berelasi dengan Daftar Masyarakat ini..."
		)
           
		gis_list = frappe.get_all(
			"GIS",
			filters={
				"pemilik_lahan": self.name
			},
			fields=["name"]
		)

		for gis in gis_list:
			frappe.db.set_value(
				"GIS",
				gis.name,
				"perangkat_desa",
				self.pd
			)
