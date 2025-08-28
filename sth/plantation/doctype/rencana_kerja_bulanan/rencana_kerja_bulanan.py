# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import format_date

from frappe.model.document import Document

from sth.utils import validate_overlap

class RencanaKerjaBulanan(Document):
	
	def autoname(self):
		self.name = f'{self.unit}-{format_date(self.from_date, "MMM-yyyy")}'

	def validate(self):
		validate_overlap(self, self.from_date, self.to_date, company=self.company, for_field="unit")
