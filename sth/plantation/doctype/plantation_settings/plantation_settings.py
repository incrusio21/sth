# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PlantationSettings(Document):
	
	def get_incentive_absent(self):
		if not getattr(self, "_absent_incentive", None):
			self._absent_incentive = frappe._dict({
				"salary_component": self.sc_incentive_absent,
				"unit": {}
			})

			for d in self.incentive_absent:
				self._absent_incentive["unit"].setdefault(d.unit, []).append({
					"max_absent": d.max_absent,
					"value": d.tarif,
				})

		return self._absent_incentive
	
	def get_incentive_output(self):
		if not getattr(self, "_output_incentive", None):
			self._output_incentive = frappe._dict({
				"salary_component": self.sc_incentive_output,
				"unit": {}
			})

			for d in self.incentive_output:
				self._output_incentive["unit"].setdefault(d.unit, []).append({
					"min_output": d.min_output,
					"value": d.tarif,
				})


		return self._output_incentive
