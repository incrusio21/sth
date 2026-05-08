# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Unit(Document):
	def validate(self):
		pass

# def debug():
# 	l = frappe.db.sql(""" SELECT name FROM `tabUnit` WHERE jenis IS NULL """)
# 	for row in l:
# 		self = frappe.get_doc("Unit", row[0])
# 		if self.plasma == 1:
# 			self.jenis = "Plasma"
# 		elif self.plantation == 1:
# 			self.jenis = "Plantation"
# 		elif self.mill == 1:
# 			self.jenis = "Mill"
# 		self.db_update()
 	