# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

from sth.hr_customize import get_allowance_settings

class LoanProduct:
	def __init__(self, doc, method):
		self.doc = doc
		self.method = method

		match self.method:
			case "validate":
				self.validate_subsidy_component()

	def validate_subsidy_component(self):
		allowance_settings = get_allowance_settings()

		self.doc.subsidy_component = allowance_settings.subsidy_component
		self.doc.against_subsidy_component = allowance_settings.against_subsidy_component
		self.doc.monthly_subsidy_component = allowance_settings.monthly_subsidy_component