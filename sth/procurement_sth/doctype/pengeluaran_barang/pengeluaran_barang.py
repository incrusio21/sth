# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc


class PengeluaranBarang(Document):
	def on_submit(self):
		self.create_ste()
	
	def create_ste(self):
		def postprocess(source,target):
			pass
		
		mapper = {

		}

		doc = get_mapped_doc("Permintaan Pengeluaran Barang",self.no_permintaan_pengeluaran,mapper,None,postprocess)