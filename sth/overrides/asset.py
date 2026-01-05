import frappe
from erpnext.assets.doctype.asset.asset import Asset
from frappe import _
from frappe.utils import (
	cint,
	flt,
	get_datetime,
	get_last_day,
	get_link_to_form,
	getdate,
	nowdate,
	today,
)

class Asset(Asset):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from erpnext.assets.doctype.asset_finance_book.asset_finance_book import AssetFinanceBook
		from frappe.types import DF

		additional_asset_cost: DF.Currency
		amended_from: DF.Link | None
		asset_category: DF.Link | None
		asset_name: DF.Data
		asset_owner: DF.Literal["", "Company", "Supplier", "Customer"]
		asset_owner_company: DF.Link | None
		asset_quantity: DF.Int
		available_for_use_date: DF.Date | None
		booked_fixed_asset: DF.Check
		calculate_depreciation: DF.Check
		company: DF.Link
		comprehensive_insurance: DF.Data | None
		cost_center: DF.Link | None
		custodian: DF.Link | None
		customer: DF.Link | None
		default_finance_book: DF.Link | None
		department: DF.Link | None
		depr_entry_posting_status: DF.Literal["", "Successful", "Failed"]
		depreciation_method: DF.Literal["", "Straight Line", "Double Declining Balance", "Manual"]
		disposal_date: DF.Date | None
		finance_books: DF.Table[AssetFinanceBook]
		frequency_of_depreciation: DF.Int
		gross_purchase_amount: DF.Currency
		image: DF.AttachImage | None
		insurance_end_date: DF.Date | None
		insurance_start_date: DF.Date | None
		insured_value: DF.Data | None
		insurer: DF.Data | None
		is_composite_asset: DF.Check
		is_existing_asset: DF.Check
		is_fully_depreciated: DF.Check
		item_code: DF.Link
		item_name: DF.ReadOnly | None
		journal_entry_for_scrap: DF.Link | None
		location: DF.Link
		maintenance_required: DF.Check
		naming_series: DF.Literal["ACC-ASS-.YYYY.-"]
		next_depreciation_date: DF.Date | None
		opening_accumulated_depreciation: DF.Currency
		opening_number_of_booked_depreciations: DF.Int
		policy_number: DF.Data | None
		purchase_amount: DF.Currency
		purchase_date: DF.Date
		purchase_invoice: DF.Link | None
		purchase_invoice_item: DF.Data | None
		purchase_receipt: DF.Link | None
		purchase_receipt_item: DF.Data | None
		split_from: DF.Link | None
		status: DF.Literal["Draft", "Submitted", "Partially Depreciated", "Fully Depreciated", "Sold", "Scrapped", "In Maintenance", "Out of Order", "Issue", "Receipt", "Capitalized", "Work In Progress"]
		supplier: DF.Link | None
		total_asset_cost: DF.Currency
		total_number_of_depreciations: DF.Int
		value_after_depreciation: DF.Currency
	# end: auto-generated types
	def make_asset_movement(self):
		reference_doctype = "Purchase Receipt" if self.purchase_receipt else "Purchase Invoice"
		reference_docname = self.purchase_receipt or self.purchase_invoice
		transaction_date = getdate(self.purchase_date)
		if reference_docname:
			posting_date, posting_time = frappe.db.get_value(
				reference_doctype, reference_docname, ["posting_date", "posting_time"]
			)
			transaction_date = get_datetime(f"{posting_date} {posting_time}")
		assets = [
			{
				"asset": self.name,
				"asset_name": self.asset_name,
				"target_location": self.location,	
				"target_unit": self.unit,
				"to_employee": self.custodian,
			}
		]
		asset_movement = frappe.get_doc(
			{
				"doctype": "Asset Movement",
				"assets": assets,
				"purpose": "Receipt",
				"company": self.company,
				"transaction_date": transaction_date,
				"reference_doctype": reference_doctype,
				"reference_name": reference_docname,
			}
		).insert()
		asset_movement.submit()

@frappe.whitelist()
def make_asset_movement(assets, purpose=None):
	import json

	if isinstance(assets, str):
		assets = json.loads(assets)

	if len(assets) == 0:
		frappe.throw(_("Atleast one asset has to be selected."))

	asset_movement = frappe.new_doc("Asset Movement")
	asset_movement.quantity = len(assets)
	if purpose:
		asset_movement.purpose = purpose

	for asset in assets:
		asset = frappe.get_doc("Asset", asset.get("name"))
		asset_movement.company = asset.get("company")
		asset_movement.append(
			"assets",
			{
				"asset": asset.get("name"),
				"source_location": asset.get("location"),
				"from_employee": asset.get("custodian"),
				"source_unit": asset.get("unit"),
				"target_location": asset.get("location"),
			},
		)

	if asset_movement.get("assets"):
		return asset_movement.as_dict()

@frappe.whitelist()
def get_values_from_purchase_doc(purchase_doc_name, item_code, doctype):
	purchase_doc = frappe.get_doc(doctype, purchase_doc_name)
	matching_items = [item for item in purchase_doc.items if item.item_code == item_code]

	if not matching_items:
		frappe.throw(_(f"Selected {doctype} does not contain the Item Code {item_code}"))

	first_item = matching_items[0]

	return {
		"company": purchase_doc.company,
		"purchase_date": purchase_doc.get("bill_date") or purchase_doc.get("posting_date"),
		"gross_purchase_amount": flt(first_item.base_net_amount / first_item.qty),
		"asset_quantity": 1,
		"cost_center": first_item.cost_center or purchase_doc.get("cost_center"),
		"asset_location": first_item.get("asset_location"),
		"purchase_receipt_item": first_item.name if doctype == "Purchase Receipt" else None,
		"purchase_invoice_item": first_item.name if doctype == "Purchase Invoice" else None,
	}
	
