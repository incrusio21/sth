# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PengajuanPanenKontanan(Document):
	
	def on_submit(self):
		self.check_status_bkm_panen()

	def on_cancel(self):
		self.check_status_bkm_panen()

	def check_status_bkm_panen(self):
		doc = frappe.get_doc("Buku Kerja Mandor Panen", self.bkm_panen)
		doc.update_kontanan_used()
