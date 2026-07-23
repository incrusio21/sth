# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe,json
from frappe.model.document import Document
from frappe.utils import flt

class AnalisaKualitasCPOProduksiHariandiPOT(Document):
	def validate(self):
		self.validate_rules()

	def validate_rules(self):
		
		rules = [
			(flt(self.tekanan_vacuum_drier) < -0.6, "Tekanan Vacuum Drier kurang dari -0.6 kg/cm2"),
			(flt(self.tekanan_vacuum_drier) > -0.9, "Tekanan Vacuum Drier lebih besar dari -0.9 kg/cm2"),
			(flt(self.ffa) > 5, "Presentase ALB Vacuum Drier(FFA) lebih besar dari 5%"),
			(flt(self.moisture) > 0.5, "Presentase Moisture lebih besar dari 0.5%"),
			(flt(self.dirt) > 0.05, "Presentase Dirt lebih besar dari 0.05%"),
			(flt(self.dobi) < 2.31, "Presentase Dobi kurang dari 2.31%"),
			(flt(self.dobi) > 3.24, "Presentase Dobi lebih besar dari 3.24%"),
		]

		errors = []
		for kondisi, pesan_error in rules:
			if kondisi:
				errors.append(pesan_error)
		
		self.warning_list = json.dumps(errors)
