# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe,json
from frappe.model.document import Document


class OilLosessOnSampel(Document):
	def validate(self):
		self.validate_rules()

	def validate_rules(self):
		
		rules = [
			(self.air_rebusan > 1 , "Presentase Air Rebusan melebihi 1%"),
			(self.fiber_bunch_press > 1.2 , "Presentase Fiber Bunch Press melebihi 1.2%"),
			(self.fiber_press > 4.5 , "Presentase Fiber Press melebihi 4.5%"),
			(self.nut_press > 0.8 , "Presentase Nut Press melebihi 0.8%"),
			(self.heavy_phase_sludge_centrifuge > 1.2 , "Presentase heavy phase centrifuge melebihi 1.2%"),
		]

		errors = []
		for kondisi, pesan_error in rules:
			if kondisi:
				errors.append(pesan_error)
		
		self.warning_list = json.dumps(errors)
