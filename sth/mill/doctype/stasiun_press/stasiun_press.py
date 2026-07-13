# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe,json
from frappe.utils import flt
from frappe.model.document import Document


class StasiunPress(Document):
	def validate(self):
		self.validate_rules()

	# def validate_rules(self):
	# 	errors = []
	# 	for i,d in enumerate(self.ampere_mesin_press):
	# 		if flt(d.hasil_inspeksi) > 130:
	# 			errors.append(f"hasil inspeksi ampere mesin press melebihi 130: row {i+1} ")
		
	# 	for i,d in enumerate(self.digester):
	# 		if d.level_digester < 3/4:
	# 			errors.append(f"level minimal level digester 3/4: row {i+1} ")

	# 		if flt(d.temprature) < 90:
	# 			errors.append(f"Temperatur kurang dari 90 C: row {i+1} ")
			
	# 	for i,d in enumerate(self.hidrolik_mesin_press):
	# 		if flt(d.hasil_inspeksi) < 40:
	# 			errors.append(f"Tekanan hidrolik kurang dari 40 kg/cm2: row {i+1} ")

	# 		if flt(d.hasil_inspeksi) > 60:
	# 			errors.append(f"Tekanan hidrolik lebih dari 60 kg/cm2: row {i+1} ")

		
	# 	self.warning_list = json.dumps(errors)

	def validate_rules(self):
		errors = []

		level_map = {
			"1/4": 0.25,
			"1/2": 0.50,
			"3/4": 0.75,
		}

		for i, d in enumerate(self.ampere_mesin_press):
			if flt(d.hasil_inspeksi) > 130:
				errors.append(f"hasil inspeksi ampere mesin press melebihi 130: row {i+1}")

		for i, d in enumerate(self.digester):
			level = level_map.get(d.level_digester, 0)

			if level < 0.75:
				errors.append(f"level minimal level digester 3/4: row {i+1}")

			if flt(d.temprature) < 90:
				errors.append(f"Temperatur kurang dari 90 C: row {i+1}")

		for i, d in enumerate(self.hidrolik_mesin_press):
			if flt(d.hasil_inspeksi) < 40:
				errors.append(f"Tekanan hidrolik kurang dari 40 kg/cm2: row {i+1}")

			if flt(d.hasil_inspeksi) > 60:
				errors.append(f"Tekanan hidrolik lebih dari 60 kg/cm2: row {i+1}")

		self.warning_list = json.dumps(errors)