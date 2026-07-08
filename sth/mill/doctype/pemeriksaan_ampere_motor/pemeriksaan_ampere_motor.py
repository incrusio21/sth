# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe,json
from frappe.model.document import Document


class PemeriksaanAmpereMotor(Document):
	def validate_rules(self):
		# Ampere > 130 Amp
		# % Oil losses > 1.2 %
		# % Kandungan Air > 55 %
		# % Kandungan Minyak <> 5 - 10 %


		rules = [
			(self.p_mth >= 5, "Presentase TBS mentah melebihi 5%"),
			(self.p_msk <= 92, "Presentase TBS masak kurang dari 92%"),
			(self.brd_b_perc >= 3, "Persentase TBS Busuk melebihi 3%"),
			(self.p_tp <= 1, "Persentase tangkai panjang kurang dari 1%"),
		]

		errors = []
		for kondisi, pesan_error in rules:
			if kondisi:
				errors.append(pesan_error)
		
		self.warning_list = json.dumps(errors)