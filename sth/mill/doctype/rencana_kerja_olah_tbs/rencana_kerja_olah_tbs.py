# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt

class RencanaKerjaOlahTBS(Document):

	def validate(self):
		self.set_total_volume_tbs()

	def set_total_volume_tbs(self):

		restan = flt(self.jumlah_tbs_restan)
		kebun = flt(self.jumlah_taksasi_tbs_kebun)
		luar = flt(self.jumlah_taksasi_tbs_luar)

		self.total_volume_tbs = restan + kebun + luar