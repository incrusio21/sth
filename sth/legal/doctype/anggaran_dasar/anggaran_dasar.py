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
		self.set_per_ownership_saham()

	def validate_mandatory_kriteria(self):
		if not self.kriteria:
			frappe.throw("Kriteria atleast need One data.")

	def clear_akta_list(self):
		self.akta_saham = self.akta_pengurus = self.akta_kriteria = None

	def calculate_saham(self):
		grand_total = total_lembar_saham = 0
		precision = frappe.get_precision("Detail Form Saham", "amount")
		for sh in self.saham:
			saham_amount = flt(sh.rate * sh.qty, precision)
			agio_amount = flt(sh.agio_rate * sh.qty, precision)
			sh.amount = flt(saham_amount + agio_amount, precision)
			grand_total += sh.amount
			total_lembar_saham += sh.qty

		self.grand_total = flt(grand_total, self.precision("grand_total"))
		self.total_lembar_saham = flt(total_lembar_saham, self.precision("total_lembar_saham"))

	def set_per_ownership_saham(self):
		for sh in self.saham:
			sh.per_ownership_saham = flt(sh.qty/self.total_lembar_saham*100, self.precision("total_lembar_saham"))