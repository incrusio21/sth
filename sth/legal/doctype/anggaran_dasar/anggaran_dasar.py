# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt

from frappe.model.document import Document

class AnggaranDasar(Document):
	
	def validate(self):
		self.validate_mandatory_kriteria()
		# self.clear_akta_list()
		self.calculate_saham()

	def validate_mandatory_kriteria(self):
		if not self.kriteria:
			frappe.throw("Kriteria atleast need One data.")

	def clear_akta_list(self):
		self.akta_saham = self.akta_pengurus = self.akta_kriteria = None

	def calculate_saham(self):
		grand_total = 0
		precision = frappe.get_precision("Detail Form Saham", "amount")
		for sh in self.saham:
			sh.amount = flt(sh.rate * sh.qty, precision)
			grand_total += sh.amount

		self.grand_total = flt(grand_total, self.precision("grand_total"))