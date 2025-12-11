# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import today
from frappe.model.document import Document


class LaporanPenerimaanTBS(Document):
	@frappe.whitelist()
	def get_timbangan(self):
		data_timbangan = frappe.db.sql("""
			select t.name as timbangan, ti.item_code, ti.item_name,ti.bruto,ti.netto,ti.tara 
			from `tabTimbangan` t
			join `tabTimbangan Item` ti on ti.parent = t.name
			where t.posting_date = %s and t.receive_type = %s and t.docstatus = 1
		""",[today(),self.tipe],as_dict=True)

		self.items = []
		for row in data_timbangan:
			child = self.append("items")
			child.update(row)
