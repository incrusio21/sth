# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe,json
from frappe.utils import time_diff_in_seconds
from frappe.model.document import Document


class SterilizerTransaction(Document):
	def validate(self):
		pass


	def validate_rules(self):
		# Tekanan Puncak I : < 1.5 Kg/Cm2, Tekanan Puncak II : < 2.8 Kg/Cm2, 
		# Waktu 70 - 90 menit Setiap Perebusan

		errors = []
		for idx, val in enumerate(self.sterilizer_transaction_monitoring):
			time_diff = abs(time_diff_in_seconds(val.time_start,val.time_stop)) / 60

			if idx == 0 and val.sterilizer_pressure < 1.5:
				errors.append("Tekanan Puncak 1 kurang dari 1.5")

			if idx == 1 and val.sterilizer_pressure < 2.8:
				errors.append("Tekanan Puncak 2 kurang dari 2.8")
			
			if not 70 <= time_diff <= 90:
				errors.append(f"Tekanan Puncak {val.idx} tidak memenuhi waktu normal(70 - 90 menit) : {time_diff} menit")

		
		self.warning_list = json.dumps(errors)