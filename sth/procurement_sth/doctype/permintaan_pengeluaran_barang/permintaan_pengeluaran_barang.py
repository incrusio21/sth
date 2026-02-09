# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from sth.controllers.queries import get_fields
from frappe.desk.reportview import get_filters_cond

class PermintaanPengeluaranBarang(Document):
	def validate(self):
		pass
		# if len(self.items) > 1:
		# 	frappe.throw("Pengeluaran lebih dari 1 jenis barang tidak diperbolehkan.")

	def on_submit(self):
		self.db_set("status","Submitted")
	
	def update_outgoing_percentage(self):
		qty = 0
		out_qty = 0

		for row in self.items:
			qty += row.jumlah
			out_qty += row.jumlah_keluar
		
		outgoing_percent = out_qty/qty * 100

		self.db_set("outgoing",outgoing_percent)


	def update_status(self):
		self.update_outgoing_percentage()

		if self.outgoing == 100:
			self.db_set("status","Barang Telah Dikeluarkan")
		elif self.outgoing > 0:
			self.db_set("status","Sebagian di Keluarkan")
		
@frappe.whitelist()
def close_status(name):
	frappe.db.set_value("Permintaan Pengeluaran Barang",name,"status","Closed")

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def filter_divisi(doctype, txt, searchfield, start, page_len, filters):
	conditions = []
	fields = ", ".join(get_fields(doctype, ["name"]))
	custom_cond = ""
	if filters.get("warehouse"):
		unit = frappe.db.get_value("Warehouse",filters.get("warehouse"), ["unit"])
		custom_cond = f" And `tabDivisi`.unit = '{unit}'"
	
	return frappe.db.sql(
		f"""
			select {fields} from `tabDivisi`
			where `tabDivisi`.{searchfield} like %(txt)s {custom_cond}
			order by
				(case when locate(%(_txt)s, `tabDivisi`.name) > 0 then locate(%(_txt)s, `tabDivisi`.name) else 99999 end),
				`tabDivisi`.name
			limit %(page_len)s offset %(start)s
		""",
		{"txt": "%%%s%%" % txt, "_txt": txt.replace("%", ""), "start": start, "page_len": page_len}
	)