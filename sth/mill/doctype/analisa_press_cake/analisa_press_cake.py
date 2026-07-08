# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe,json
from frappe.model.document import Document


class AnalisaPressCake(Document):
	def validate(self):
		self.validate_rules()

	def validate_rules(self):
		
		rules = [
			(self.nut_pecah_press_cake > 9 , "Presentase nut pecah melebihi 9%"),
			(self.nut_to_press_cake < 45 , "Presentase nut to press cake kurang dari 45%"),
			(self.nut_to_press_cake > 55 , "Presentase nut to press cake melebihi 55%"),
		]

		errors = []
		for kondisi, pesan_error in rules:
			if kondisi:
				errors.append(pesan_error)
		
		self.warning_list = json.dumps(errors)
