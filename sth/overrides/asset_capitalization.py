import frappe
from erpnext.assets.doctype.asset_capitalization.asset_capitalization import AssetCapitalization
from erpnext.assets.doctype.asset_activity.asset_activity import add_asset_activity
from erpnext.assets.doctype.asset_category.asset_category import get_asset_category_account
from frappe.utils import cint, flt, get_link_to_form
from frappe import _


@frappe.whitelist()
def get_bapp_from_project(project):
	"""Return all submitted BAPPs linked to any Proposal under the given Project."""
	proposals = frappe.get_all(
		"Proposal",
		filters={"project": project, "docstatus": 1},
		pluck="name",
	)
	if not proposals:
		return []

	bapps = frappe.get_all(
		"BAPP",
		filters={"proposal": ["in", proposals], "docstatus": 1},
		fields=["name", "supplier", "supplier_name", "proposal", "project", "grand_total", "status"],
	)
	return bapps


@frappe.whitelist()
def get_bapp_from_proposal(proposal):
	"""Return all submitted BAPPs linked to the given Proposal."""
	bapps = frappe.get_all(
		"BAPP",
		filters={"proposal": proposal, "docstatus": 1},
		fields=["name", "supplier", "supplier_name", "proposal", "project", "grand_total", "status"],
	)
	return bapps

class AssetCapitalization(AssetCapitalization):

	# ------------------------------------------------------------------
	# Totals: ikut sertakan asset_capitalization_bapp_item_total ke total_value
	# ------------------------------------------------------------------
	def calculate_totals(self):
		super().calculate_totals()

		self.asset_capitalization_bapp_item_total = flt(
			sum(flt(row.grand_total) for row in self.get("asset_capitalization_bapp_item")),
			self.precision("total_value"),
		)

		self.total_value = flt(
			flt(self.total_value) + self.asset_capitalization_bapp_item_total,
			self.precision("total_value"),
		)

		if self.target_qty:
			self.target_incoming_rate = self.total_value / flt(self.target_qty)

	# ------------------------------------------------------------------
	# GL Entries: tambah BAPP items ke pipeline GL
	# ------------------------------------------------------------------
	def get_gl_entries(self, warehouse_account=None, default_expense_account=None, default_cost_center=None):
		gl_entries = super().get_gl_entries(
			warehouse_account=warehouse_account,
			default_expense_account=default_expense_account,
			default_cost_center=default_cost_center,
		)

		if self.get("asset_capitalization_bapp_item"):
			precision = self.get_debit_field_precision()
			target_account = self.get_target_account()
			target_against = set()

			self.get_gl_entries_for_asset_capitalization_bapp_item(gl_entries, target_account, target_against, precision)

		return gl_entries

	def get_gl_entries_for_asset_capitalization_bapp_item(self, gl_entries, target_account, target_against, precision):
		"""Credit expense_account per item dari setiap BAPP."""
		for bapp_row in self.get("asset_capitalization_bapp_item"):
			if not bapp_row.bapp:
				continue

			bapp_doc = frappe.get_doc("BAPP", bapp_row.bapp)

			for item in bapp_doc.get("items"):
				amount = flt(item.get("base_amount") or item.get("amount"), precision)
				expense_account = item.get("expense_account")

				if not amount or not expense_account:
					continue

				target_against.add(expense_account)

				gl_entries.append(
					self.get_gl_dict(
						{
							"account": expense_account,
							"against": target_account,
							"credit": amount,
							"cost_center": item.get("cost_center") or self.get("cost_center"),
							"project": bapp_row.get("project") or self.get("project"),
							"remarks": self.get("remarks") or _("Accounting Entry for BAPP"),
						},
						item=item,
					)
				)

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
		asset_doc.total_depreciation_fiscal = 12
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