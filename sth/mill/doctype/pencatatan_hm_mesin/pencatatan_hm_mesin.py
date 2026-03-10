# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt

class PencatatanHMMesin(Document):

	def validate(self):

		awal = flt(self.hm_mesin_awal)
		akhir = flt(self.hm_mesin_akhir)

		self.total_hm_mesin = akhir - awal