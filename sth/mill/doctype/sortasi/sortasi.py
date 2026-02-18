# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Sortasi(Document):
	def before_submit(self):
		tim_doc = frappe.get_doc("Timbangan", self.no_timbangan)
		if self.tipe == "External":
			potongan_sortasi = self.potongan_sortasi_external
		else:
			potongan_sortasi = self.potongan_sortasi_internal

		tim_doc.potongan_sortasi = potongan_sortasi
		tim_doc.netto_2 = tim_doc.netto - (tim_doc.netto * tim_doc.potongan_sortasi / 100)
		tim_doc.db_update()
