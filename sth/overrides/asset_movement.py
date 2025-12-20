from erpnext.assets.doctype.asset_movement.asset_movement import AssetMovement
from erpnext.assets.doctype.asset_activity.asset_activity import add_asset_activity
from frappe.utils import get_link_to_form
from frappe import _
import frappe

class AssetMovement(AssetMovement):
	def log_asset_activity(self, asset_id, location, employee):
		if location and employee:
			add_asset_activity(
				asset_id,
				_("Asset received at Unit {0} and issued to Employee {1}").format(
					get_link_to_form("Unit", location),
					get_link_to_form("Employee", employee),
				),
			)
		elif location:
			add_asset_activity(
				asset_id,
				_("Asset transferred to Unit {0}").format(get_link_to_form("Unit", location)),
			)
		elif employee:
			add_asset_activity(
				asset_id,
				_("Asset issued to Employee {0}").format(get_link_to_form("Employee", employee)),
			)

	def validate_location(self, d):
		if self.purpose in ["Transfer", "Transfer and Issue"]:
			current_location = frappe.db.get_value("Asset", d.asset, "unit")
			if d.source_unit:
				if current_location != d.source_unit:
					frappe.throw(
						_("Asset {0} does not belongs to the unit {1}").format(d.asset, d.source_unit)
					)
			else:
				d.source_unit = current_location
			if not d.target_unit:
				frappe.throw(_("Target Unit is required for transferring Asset {0}").format(d.asset))
			if d.source_unit == d.target_unit:
				frappe.throw(_("Source and Target Unit cannot be same"))

		if self.purpose == "Receipt":
			if not d.target_unit:
				frappe.throw(_("Target Unit is required while receiving Asset {0}").format(d.asset))
			if d.to_employee and frappe.db.get_value("Employee", d.to_employee, "company") != self.company:
				frappe.throw(
					_("Employee {0} does not belongs to the company {1}").format(d.to_employee, self.company)
				)


	def set_latest_location_and_custodian_in_asset(self):
		for d in self.assets:
			current_location, current_employee, current_unit = self.get_latest_location_and_custodian_custom(d.asset)
			self.update_asset_location_and_custodian(d.asset, current_location, current_employee, current_unit)
			self.log_asset_activity(d.asset, current_location, current_employee)

	def get_latest_location_and_custodian_custom(self, asset):
		current_location, current_employee = "", ""
		cond = "1=1"

		# latest entry corresponds to current document's location, employee when transaction date > previous dates
		# In case of cancellation it corresponds to previous latest document's location, employee
		args = {"asset": asset, "company": self.company}
		latest_movement_entry = frappe.db.sql(
			f"""
			SELECT asm_item.target_location, asm_item.to_employee, asm_item.target_unit
			FROM `tabAsset Movement Item` asm_item
			JOIN `tabAsset Movement` asm ON asm_item.parent = asm.name
			WHERE
				asm_item.asset = %(asset)s AND
				asm.company = %(company)s AND
				asm.docstatus = 1 AND {cond}
			ORDER BY asm.transaction_date DESC
			LIMIT 1
			""",
			args,
		)

		if latest_movement_entry:
			current_location = latest_movement_entry[0][0]
			current_employee = latest_movement_entry[0][1]
			current_unit = latest_movement_entry[0][2]

		return current_location, current_employee, current_unit

	def update_asset_location_and_custodian(self, asset_id, location, employee, unit):
		asset = frappe.get_doc("Asset", asset_id)

		if employee and employee != asset.custodian:
			frappe.db.set_value("Asset", asset_id, "custodian", employee)
		if location and location != asset.location:
			frappe.db.set_value("Asset", asset_id, "location", location)
		if unit and unit != asset.unit:
			frappe.db.set_value("Asset", asset_id, "unit", unit)