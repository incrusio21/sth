# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

BULAN_MAP = {
	"Januari": 1,
	"Februari": 2,
	"Maret": 3,
	"April": 4,
	"Mei": 5,
	"Juni": 6,
	"Juli": 7,
	"Agustus": 8,
	"September": 9,
	"Oktober": 10,
	"November": 11,
	"Desember": 12,
}

class Blok(Document):
	def validate(self):
		self.set_periode_bjr()

	def before_save(self):
		self.set_periode_bjr()

	def after_insert(self):
		self.make_cost_center()

	def on_update(self):
		self.make_cost_center()

	def make_cost_center(self):
		if not self.tahun_tanam or not self.unit:
			return

		cc_name = str(self.tahun_tanam)

		if frappe.db.exists("Cost Center", {"cost_center_name": cc_name, "company":  frappe.get_doc("Unit", self.unit).company}):
			return

		company_doc = frappe.get_doc("Company", frappe.get_doc("Unit", self.unit).company)

		cc = frappe.new_doc("Cost Center")
		cc.cost_center_name = cc_name
		cc.parent_cost_center = f"Tahun Tanam - {company_doc.abbr}"
		cc.company = frappe.get_doc("Unit", self.unit).company
		cc.is_group = 0
		cc.flags.ignore_permissions = True
		cc.insert()
		frappe.db.commit()

	def set_periode_bjr(self):
		if self.bulan and self.tahun:
			bulan_angka = BULAN_MAP.get(self.bulan)
			if bulan_angka:
				# Format: YYYY-MM-DD HH:MM:SS (format internal ERPNext)
				self.periode_bjr = "{}-{:02d}-01 00:00:00".format(
					int(self.tahun), bulan_angka
				)
