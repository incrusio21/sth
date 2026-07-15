# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class AlatBeratDanKendaraan(Document):

	def after_insert(self):
		self.make_cost_center()

	def on_update(self):
		self.make_cost_center()

	def make_cost_center(self):
		if not self.name or not self.company:
			return

		if frappe.db.exists(
			"Cost Center",
			{"cost_center_name": self.name, "company": self.company}
		):
			self.cost_center = "{} - {}".format(self.name, frappe.get_doc("Company", self.company).abbr)
			frappe.db.commit()
			return

		company_doc = frappe.get_doc("Company", self.company)

		root_parent = f"{company_doc.company_name} - {company_doc.abbr}"
		vra_parent = f"VRA - {company_doc.abbr}"

		if not frappe.db.exists("Cost Center", vra_parent):
			parent = frappe.new_doc("Cost Center")
			parent.cost_center_name = "VRA"
			parent.parent_cost_center = root_parent
			parent.company = self.company
			parent.is_group = 1
			parent.flags.ignore_permissions = True
			parent.insert()

		cc = frappe.new_doc("Cost Center")
		cc.cost_center_name = self.name
		cc.parent_cost_center = vra_parent
		cc.company = self.company
		cc.is_group = 0
		cc.flags.ignore_permissions = True
		cc.insert()

		self.cost_center = cc.name
		frappe.db.commit()
