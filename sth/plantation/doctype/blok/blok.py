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

	def set_periode_bjr(self):
		if self.bulan and self.tahun:
			bulan_angka = BULAN_MAP.get(self.bulan)
			if bulan_angka:
				# Format: YYYY-MM-DD HH:MM:SS (format internal ERPNext)
				self.periode_bjr = "{}-{:02d}-01 00:00:00".format(
					int(self.tahun), bulan_angka
				)
