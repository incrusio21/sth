# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe,json
from frappe.utils import flt
from frappe.model.document import Document


class PemeriksaanTemperaturTangkiTangki(Document):
	def validate(self):
		self.validate_rules()
	
	def before_submit(self):
		self.status = "Selesai"
	
	def validate_rules(self):
		
		rules = [
			(flt(self.temperatur_cot) < 90 , "Temperatur (COT) kurang dari 90 derajat celcius"),
			(flt(self.temperatur_cst) > 90 , "Temperatur (CST) melebihi 90 derajat celcius"),
			(flt(self.ketebalan_minyak) < 30 , "Ketebalan minyak (CST) kurang dari 30 Cm"),
			(flt(self.ketebalan_minyak) > 100 , "Ketebalan minyak (CST) lebih dari 100 Cm"),
		]

		errors = []
		for kondisi, pesan_error in rules:
			if kondisi:
				errors.append(pesan_error)
		
		self.warning_list = json.dumps(errors)
