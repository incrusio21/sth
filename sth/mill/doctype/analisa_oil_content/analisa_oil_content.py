# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe,json
from frappe.model.document import Document


class AnalisaOilContent(Document):
	def validate(self):
		self.validate_rules()

	def validate_rules(self):
		
		rules = [
			(self.kadar_air_liquor > 55 , "Presentase Kandungan Air melebihi 55%"),
			(self.oil_liquor > 10 , "Presentase Kandungan Minyak melebihi 10%"),
			(self.oil_liquor < 5 , "Presentase Kandungan Minyak kurang dari 5%"),
			(self.oil_cot < 30 , "Presentase Oil Content kurang dari 30%"),
			(self.oil_cot > 35 , "Presentase Oil Content lebih dari 35%"),
			(self.oil_underflow > 8 , "Presentase Oil Underflow lebih dari 8%"),
			(self.moist_cot > 0.5 , "Presentase Moist COT lebih dari 0.5%"),
			(self.emulsi_cot > 0.5 , "Presentase Emulsi COT lebih dari 0.5%"),
			(self.nos_cot > 0.05 , "Presentase Nos COT lebih dari 0.05%"),
		]

		errors = []
		for kondisi, pesan_error in rules:
			if kondisi:
				errors.append(pesan_error)
		
		self.warning_list = json.dumps(errors)
