# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from frappe.utils import cint
from frappe.model.document import Document


class ProposalType(Document):
	def validate(self):
		self.validate_columns_width()

	def validate_columns_width(self):
		total_column_width = 0.0
		for row in self.fields:
			if not row.columns:
				frappe.throw(_("Column width cannot be zero."))

			total_column_width += cint(row.columns)

		if total_column_width and total_column_width > 10:
			frappe.throw(_("The total column width cannot be more than 10."))
