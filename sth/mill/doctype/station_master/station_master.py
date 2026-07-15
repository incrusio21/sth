# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe,json
from frappe.model.document import Document
from sth.utils.qr_generator import get_qr_svg

class StationMaster(Document):
	# def validate(self):
	# 	from sth.utils.qr_generator import generate_qr_for_doc
	# 	generate_qr_for_doc(self,1)
    
	def after_insert(self):
		self.create_cost_centers()

	def create_cost_centers(self):
		for row in self.detail_station_settings:
			if not row.unit:
				continue

			unit_doc = frappe.get_doc("Unit", row.unit)
			company = unit_doc.company
			company_doc = frappe.get_doc("Company", company)
			parent_cost_center = f"Station - {company_doc.abbr}"

			existing = frappe.db.get_value(
				"Cost Center",
				{"cost_center_name": self.machine_name, "company": company},
				"name"
			)

			cc_name = existing
			if not existing:
				cc = frappe.new_doc("Cost Center")
				cc.cost_center_name = self.machine_name
				cc.parent_cost_center = parent_cost_center
				cc.company = company
				cc.is_group = 0
				cc.flags.ignore_permissions = True
				cc.insert()
				frappe.db.commit()
				cc_name = cc.name

			frappe.db.set_value("Detail Station Master", row.name, "cost_center", cc_name, update_modified=False)

	def before_save(self):
		self.create_qr_unit()

	def create_qr_unit(self):
		for row in self.detail_station_settings:
			data = {"stasiun": self.name, "unit" : row.unit , "latitude": row.latitude , "longitude": row.longitude }
			row.qr_code = get_qr_svg(json.dumps(data))