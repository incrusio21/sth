from erpnext.assets.doctype.asset_movement.asset_movement import AssetMovement
from erpnext.assets.doctype.asset_activity.asset_activity import add_asset_activity
from frappe.utils import get_link_to_form

class AssetMovement(AssetMovement):
	def log_asset_activity(self, asset_id, location, employee):
		if location and employee:
			add_asset_activity(
				asset_id,
				_("Asset received at Location {0} and issued to Employee {1}").format(
					get_link_to_form("Unit", location),
					get_link_to_form("Employee", employee),
				),
			)
		elif location:
			add_asset_activity(
				asset_id,
				_("Asset transferred to Location {0}").format(get_link_to_form("Unit", location)),
			)
		elif employee:
			add_asset_activity(
				asset_id,
				_("Asset issued to Employee {0}").format(get_link_to_form("Employee", employee)),
			)
