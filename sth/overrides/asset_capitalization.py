import frappe
from erpnext.assets.doctype.asset_capitalization.asset_capitalization import AssetCapitalization
from erpnext.assets.doctype.asset_activity.asset_activity import add_asset_activity
from erpnext.assets.doctype.asset_category.asset_category import get_asset_category_account
from frappe.utils import cint, flt, get_link_to_form
from frappe import _

class AssetCapitalization(AssetCapitalization):

	def validate_source_mandatory(self):
		return

		# if self.capitalization_method == "Create a new composite asset" and not (
		# 	self.get("stock_items") or self.get("asset_items")
		# ):
		# 	frappe.throw(
		# 		_(
		# 			"Consumed Stock Items or Consumed Asset Items are mandatory for creating new composite asset"
		# 		)
		# 	)

		# elif not (self.get("stock_items") or self.get("asset_items") or self.get("service_items")):
		# 	frappe.throw(
		# 		_(
		# 			"Consumed Stock Items, Consumed Asset Items or Consumed Service Items is mandatory for Capitalization"
		# 		)
		# 	)

	def create_target_asset(self):
		if self.capitalization_method != "Create a new composite asset":
			return

		total_target_asset_value = flt(self.total_value, self.precision("total_value"))

		asset_doc = frappe.new_doc("Asset")
		asset_doc.company = self.company
		asset_doc.item_code = self.target_item_code
		asset_doc.is_composite_asset = 1
		asset_doc.location = self.target_asset_location
		asset_doc.available_for_use_date = self.posting_date
		asset_doc.purchase_date = self.posting_date
		asset_doc.gross_purchase_amount = total_target_asset_value
		asset_doc.purchase_amount = total_target_asset_value
		asset_doc.flags.ignore_validate = True
		asset_doc.flags.asset_created_via_asset_capitalization = True

		asset_doc.unit = self.unit

		asset_doc.insert()

		self.target_asset = asset_doc.name

		self.target_fixed_asset_account = get_asset_category_account(
			"fixed_asset_account", item=self.target_item_code, company=asset_doc.company
		)
		asset_doc.set_status("Work In Progress")

		add_asset_activity(
			asset_doc.name,
			_("Asset created after Asset Capitalization {0} was submitted").format(
				get_link_to_form("Asset Capitalization", self.name)
			),
		)

		frappe.msgprint(
			_("Asset {0} has been created. Please set the depreciation details if any and submit it.").format(
				get_link_to_form("Asset", asset_doc.name)
			)
		)