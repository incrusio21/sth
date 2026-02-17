# Copyright (c) 2026, DAS and Contributors
# License: GNU General Public License v3. See license.txt


import frappe
from frappe import _, throw
from frappe.desk.notifications import clear_doctype_notifications
from frappe.model.mapper import get_mapped_doc
from frappe.query_builder.functions import CombineDatetime
from frappe.utils import cint, flt, get_datetime, getdate, nowdate
from pypika import functions as fn

import erpnext
from erpnext.accounts.utils import get_account_currency
from erpnext.assets.doctype.asset.asset import get_asset_account, is_cwip_accounting_enabled
from erpnext.buying.utils import check_on_hold_or_closed_status
from erpnext.controllers.accounts_controller import merge_taxes
from erpnext.controllers.buying_controller import BuyingController
from erpnext.stock.doctype.delivery_note.delivery_note import make_inter_company_transaction

form_grid_templates = {"items": "templates/form_grid/item_grid.html"}


class BAPP(BuyingController):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from erpnext.accounts.doctype.pricing_rule_detail.pricing_rule_detail import PricingRuleDetail
		from erpnext.accounts.doctype.purchase_taxes_and_charges.purchase_taxes_and_charges import (
			PurchaseTaxesandCharges,
		)
		from erpnext.stock.doctype.purchase_receipt_item.purchase_receipt_item import PurchaseReceiptItem

		additional_discount_percentage: DF.Float
		address_display: DF.SmallText | None
		amended_from: DF.Link | None
		apply_discount_on: DF.Literal["", "Grand Total", "Net Total"]
		apply_putaway_rule: DF.Check
		auto_repeat: DF.Link | None
		base_discount_amount: DF.Currency
		base_grand_total: DF.Currency
		base_in_words: DF.Data | None
		base_net_total: DF.Currency
		base_rounded_total: DF.Currency
		base_rounding_adjustment: DF.Currency
		base_tax_withholding_net_total: DF.Currency
		base_taxes_and_charges_added: DF.Currency
		base_taxes_and_charges_deducted: DF.Currency
		base_total: DF.Currency
		base_total_taxes_and_charges: DF.Currency
		billing_address: DF.Link | None
		billing_address_display: DF.SmallText | None
		buying_price_list: DF.Link | None
		company: DF.Link
		contact_display: DF.SmallText | None
		contact_email: DF.SmallText | None
		contact_mobile: DF.SmallText | None
		contact_person: DF.Link | None
		conversion_rate: DF.Float
		cost_center: DF.Link | None
		currency: DF.Link
		disable_rounded_total: DF.Check
		discount_amount: DF.Currency
		dispatch_address: DF.Link | None
		dispatch_address_display: DF.TextEditor | None
		grand_total: DF.Currency
		group_same_items: DF.Check
		ignore_pricing_rule: DF.Check
		in_words: DF.Data | None
		incoterm: DF.Link | None
		instructions: DF.SmallText | None
		inter_company_reference: DF.Link | None
		is_internal_supplier: DF.Check
		is_old_subcontracting_flow: DF.Check
		is_return: DF.Check
		is_subcontracted: DF.Check
		items: DF.Table[PurchaseReceiptItem]
		language: DF.Data | None
		letter_head: DF.Link | None
		lr_date: DF.Date | None
		lr_no: DF.Data | None
		named_place: DF.Data | None
		naming_series: DF.Literal["MAT-PRE-.YYYY.-", "MAT-PR-RET-.YYYY.-"]
		net_total: DF.Currency
		other_charges_calculation: DF.TextEditor | None
		per_billed: DF.Percent
		per_returned: DF.Percent
		plc_conversion_rate: DF.Float
		posting_date: DF.Date
		posting_time: DF.Time
		price_list_currency: DF.Link | None
		pricing_rules: DF.Table[PricingRuleDetail]
		project: DF.Link | None
		range: DF.Data | None
		rejected_warehouse: DF.Link | None
		remarks: DF.SmallText | None
		represents_company: DF.Link | None
		return_against: DF.Link | None
		rounded_total: DF.Currency
		rounding_adjustment: DF.Currency
		scan_barcode: DF.Data | None
		select_print_heading: DF.Link | None
		set_from_warehouse: DF.Link | None
		set_posting_time: DF.Check
		set_warehouse: DF.Link | None
		shipping_address: DF.Link | None
		shipping_address_display: DF.SmallText | None
		shipping_rule: DF.Link | None
		status: DF.Literal[
			"", "Draft", "Partly Billed", "To Bill", "Completed", "Return Issued", "Cancelled", "Closed"
		]
		subcontracting_receipt: DF.Link | None
		supplier: DF.Link
		supplier_address: DF.Link | None
		supplier_delivery_note: DF.Data | None
		supplier_name: DF.Data | None
		supplier_warehouse: DF.Link | None
		tax_category: DF.Link | None
		tax_withholding_net_total: DF.Currency
		taxes: DF.Table[PurchaseTaxesandCharges]
		taxes_and_charges: DF.Link | None
		taxes_and_charges_added: DF.Currency
		taxes_and_charges_deducted: DF.Currency
		tc_name: DF.Link | None
		terms: DF.TextEditor | None
		title: DF.Data | None
		total: DF.Currency
		total_net_weight: DF.Float
		total_qty: DF.Float
		total_taxes_and_charges: DF.Currency
		transporter_name: DF.Data | None
	# end: auto-generated types

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.status_updater = [
			{
				"target_dt": "Proposal Item",
				"join_field": "proposal_item",
				"target_field": "received_qty",
				"target_parent_dt": "Proposal",
				"target_parent_field": "per_received",
				"target_ref_field": "qty",
				"source_dt": "BAPP Item",
				"source_field": "qty",
				"percent_join_field": "proposal",
				"overflow_type": "receipt",
			},
		]

	def before_validate(self):
		from erpnext.stock.doctype.putaway_rule.putaway_rule import apply_putaway_rule

		if self.get("items") and self.apply_putaway_rule:
			apply_putaway_rule(self.doctype, self.get("items"), self.company)

	def validate(self):
		self.validate_posting_time()
		super().validate()

		if self._action != "submit":
			self.set_status()

		self.po_required()
		self.validate_items_quality_inspection()
		self.validate_with_previous_doc()
		self.validate_uom_is_integer()
		self.validate_cwip_accounts()
		self.validate_provisional_expense_account()

		self.check_on_hold_or_closed_status()

		if getdate(self.posting_date) > getdate(nowdate()):
			throw(_("Posting Date cannot be future date"))
		
	def validate_uom_is_integer(self):
		super().validate_uom_is_integer("uom", ["qty", "received_qty"], "BAPP Item")
		super().validate_uom_is_integer("stock_uom", "stock_qty", "BAPP Item")

	def validate_cwip_accounts(self):
		for item in self.get("items"):
			if item.is_fixed_asset and is_cwip_accounting_enabled(item.asset_category):
				# check cwip accounts before making auto assets
				# Improves UX by not giving messages of "Assets Created" before throwing error of not finding arbnb account
				self.get_company_default("asset_received_but_not_billed")
				get_asset_account(
					"capital_work_in_progress_account",
					asset_category=item.asset_category,
					company=self.company,
				)
				break

	def validate_provisional_expense_account(self):
		provisional_accounting_for_non_stock_items = cint(
			frappe.db.get_value("Company", self.company, "enable_provisional_accounting_for_non_stock_items")
		)

		if not provisional_accounting_for_non_stock_items:
			return

		default_provisional_account = self.get_company_default("default_provisional_account")
		for item in self.get("items"):
			if not item.get("provisional_expense_account"):
				item.provisional_expense_account = default_provisional_account

	def validate_with_previous_doc(self):
		super().validate_with_previous_doc(
			{
				"Proposal": {
					"ref_dn_field": "proposal",
					"compare_fields": [["supplier", "="], ["company", "="], ["currency", "="]],
				},
				"Proposal Item": {
					"ref_dn_field": "proposal_item",
					"compare_fields": [["project", "="], ["uom", "="], ["kegiatan", "="], ["kegiatan_name", "="]],
					"is_child_table": True,
					"allow_duplicate_prev_row_id": True,
				},
			}
		)

	def po_required(self):
		if frappe.db.get_value("Buying Settings", None, "po_required") == "Yes":
			for d in self.get("items"):
				if not d.proposal:
					frappe.throw(_("Proposal number required for Item {0}").format(d.item_code))

	def validate_items_quality_inspection(self):
		for item in self.get("items"):
			if item.quality_inspection:
				qi = frappe.db.get_value(
					"Quality Inspection",
					item.quality_inspection,
					["reference_type", "reference_name", "item_code"],
					as_dict=True,
				)

				if qi.reference_type != self.doctype or qi.reference_name != self.name:
					msg = f"""Row #{item.idx}: Please select a valid Quality Inspection with Reference Type
						{frappe.bold(self.doctype)} and Reference Name {frappe.bold(self.name)}."""
					frappe.throw(_(msg))

				if qi.item_code != item.item_code:
					msg = f"""Row #{item.idx}: Please select a valid Quality Inspection with Item Code
						{frappe.bold(item.item_code)}."""
					frappe.throw(_(msg))

	def get_already_received_qty(self, po, proposal_detail):
		qty = frappe.db.sql(
			"""select sum(qty) from `tabBAPP Item`
			where proposal_item = %s and docstatus = 1
			and proposal=%s
			and parent != %s""",
			(proposal_detail, po, self.name),
		)
		return qty and flt(qty[0][0]) or 0.0

	# Check for Closed status
	def check_on_hold_or_closed_status(self):
		check_list = []
		for d in self.get("items"):
			if d.meta.get_field("proposal") and d.proposal and d.proposal not in check_list:
				check_list.append(d.proposal)
				check_on_hold_or_closed_status("Proposal", d.proposal)

	# on submit
	def on_submit(self):
		super().on_submit()

		# Check for Approving Authority
		frappe.get_doc("Authorization Control").validate_approving_authority(
			self.doctype, self.company, self.base_grand_total
		)

		self.update_prevdoc_status()
		if flt(self.per_billed) < 100:
			self.update_billing_status()
		else:
			self.db_set("status", "Completed")

		# Updating stock ledger should always be called after updating prevdoc status,
		# because updating ordered qty, reserved_qty_for_subcontract in bin
		# depends upon updated ordered qty in PO
		self.make_gl_entries()

		self.validate_and_update_progress_received()

	def validate_and_update_progress_received(self):
		po_list = {}
		# get list po dan name itemny
		for item in self.items:
			if item.proposal and item.proposal_item:
				po_list.setdefault(item.proposal, {}).setdefault(item.proposal_item, 0)
				po_list[item.proposal][item.proposal_item] += item.qty

		for po_name, item_list in po_list.items():
			po = frappe.get_doc("Proposal", po_name, for_update=True)

			# jika po bukan submit atau bukan merupakan check progress
			if po.docstatus != 1:
				continue
			
			for po_item in po.items:
				item_qty = item_list.get(po_item.name)
				if not item_qty:
					continue

				# jika progress received lebih kecil dari persentasi received munculkan error
				if flt(po_item.progress_received) < flt(item_qty):
					frappe.throw(_(f"Progress on {po.name} at Row#{po_item.idx} cannot exceed {item_qty}"))

				# ubah progress menjadi 0
				po_item.progress_received = flt(item_qty) - flt(po_item.progress_received)

			po.update_child_table("items")

	def check_next_docstatus(self):
		submit_rv = frappe.db.sql(
			"""select t1.name
			from `tabPurchase Invoice` t1,`tabPurchase Invoice Item` t2
			where t1.name = t2.parent and t2.bapp = %s and t1.docstatus = 1""",
			(self.name),
		)
		if submit_rv:
			frappe.throw(_("Purchase Invoice {0} is already submitted").format(self.submit_rv[0][0]))

	def on_cancel(self):
		super().on_cancel()

		self.check_on_hold_or_closed_status()
		# Check if Purchase Invoice has been submitted against current Purchase Order
		submitted = frappe.db.sql(
			"""select t1.name
			from `tabPurchase Invoice` t1,`tabPurchase Invoice Item` t2
			where t1.name = t2.parent and t2.purchase_receipt = %s and t1.docstatus = 1""",
			self.name,
		)
		if submitted:
			frappe.throw(_("Purchase Invoice {0} is already submitted").format(submitted[0][0]))

		self.update_prevdoc_status()
		self.update_billing_status()

		# Updating stock ledger should always be called after updating prevdoc status,
		# because updating ordered qty in bin depends upon updated ordered qty in PO
		self.make_gl_entries_on_cancel()
		self.ignore_linked_doctypes = (
			"GL Entry",
			"Stock Ledger Entry",
			"Repost Item Valuation",
			"Serial and Batch Bundle",
		)

	def before_cancel(self):
		super().before_cancel()
		self.remove_amount_difference_with_purchase_invoice()

	def remove_amount_difference_with_purchase_invoice(self):
		for item in self.items:
			item.amount_difference_with_purchase_invoice = 0

	def get_gl_entries(self, warehouse_account=None, via_landed_cost_voucher=False):
		from erpnext.accounts.general_ledger import process_gl_map

		gl_entries = []

		self.make_item_gl_entries(gl_entries, warehouse_account=warehouse_account)
		self.make_tax_gl_entries(gl_entries, via_landed_cost_voucher)
		update_regional_gl_entries(gl_entries, self)

		return process_gl_map(gl_entries)

	def make_item_gl_entries(self, gl_entries, warehouse_account=None):
		from erpnext.accounts.doctype.purchase_invoice.purchase_invoice import (
			get_purchase_document_details,
		)

		provisional_accounting_for_non_stock_items = cint(
			frappe.db.get_value("Company", self.company, "enable_provisional_accounting_for_non_stock_items")
		)

		exchange_rate_map, net_rate_map = get_purchase_document_details(self)

		def validate_account(account_type):
			frappe.throw(_("{0} account not found while submitting BAPP").format(account_type))

		def make_item_asset_inward_gl_entry(item, stock_value_diff, stock_asset_account_name):
			account_currency = get_account_currency(stock_asset_account_name)

			if not stock_asset_account_name:
				validate_account("Asset or warehouse account")

			self.add_gl_entry(
				gl_entries=gl_entries,
				account=stock_asset_account_name,
				cost_center=d.cost_center,
				debit=stock_value_diff,
				credit=0.0,
				remarks=remarks,
				against_account=stock_asset_rbnb,
				account_currency=account_currency,
				item=item,
			)

		def make_stock_received_but_not_billed_entry(item):
			account = (
				stock_asset_rbnb
			)
			account_currency = get_account_currency(account)

			# GL Entry for from warehouse or Stock Received but not billed
			# Intentionally passed negative debit amount to avoid incorrect GL Entry validation
			credit_amount = (
				flt(item.base_net_amount, item.precision("base_net_amount"))
				if account_currency == self.company_currency
				else flt(item.net_amount, item.precision("net_amount"))
			)

			outgoing_amount = item.base_net_amount

			if credit_amount:
				if not account:
					validate_account("Stock or Asset Received But Not Billed")

				self.add_gl_entry(
					gl_entries=gl_entries,
					account=account,
					cost_center=item.cost_center,
					debit=-1 * flt(outgoing_amount, item.precision("base_net_amount")),
					credit=0.0,
					remarks=remarks,
					against_account=stock_asset_account_name,
					debit_in_account_currency=-1 * flt(outgoing_amount, item.precision("base_net_amount")),
					account_currency=account_currency,
					item=item,
				)

				# check if the exchange rate has changed
				if d.get("purchase_invoice"):
					if (
						exchange_rate_map[item.purchase_invoice]
						and self.conversion_rate != exchange_rate_map[item.purchase_invoice]
						and item.net_rate == net_rate_map[item.purchase_invoice_item]
					):
						discrepancy_caused_by_exchange_rate_difference = (item.qty * item.net_rate) * (
							exchange_rate_map[item.purchase_invoice] - self.conversion_rate
						)

						self.add_gl_entry(
							gl_entries=gl_entries,
							account=account,
							cost_center=item.cost_center,
							debit=0.0,
							credit=discrepancy_caused_by_exchange_rate_difference,
							remarks=remarks,
							against_account=self.supplier,
							debit_in_account_currency=-1 * discrepancy_caused_by_exchange_rate_difference,
							account_currency=account_currency,
							item=item,
						)

						self.add_gl_entry(
							gl_entries=gl_entries,
							account=self.get_company_default("exchange_gain_loss_account"),
							cost_center=d.cost_center,
							debit=discrepancy_caused_by_exchange_rate_difference,
							credit=0.0,
							remarks=remarks,
							against_account=self.supplier,
							debit_in_account_currency=-1 * discrepancy_caused_by_exchange_rate_difference,
							account_currency=account_currency,
							item=item,
						)

			return outgoing_amount

		def make_amount_difference_entry(item):
			if item.amount_difference_with_purchase_invoice and stock_asset_rbnb:
				account_currency = get_account_currency(stock_asset_rbnb)
				self.add_gl_entry(
					gl_entries=gl_entries,
					account=stock_asset_rbnb,
					cost_center=item.cost_center,
					debit=0.0,
					credit=flt(item.amount_difference_with_purchase_invoice),
					remarks=_("Adjustment based on Purchase Invoice rate"),
					against_account=stock_asset_account_name,
					account_currency=account_currency,
					project=item.project,
					item=item,
				)

		def make_divisional_loss_gl_entry(item, outgoing_amount):
			if item.is_fixed_asset:
				return

			# divisional loss adjustment
			valuation_amount_as_per_doc = (
				flt(outgoing_amount, d.precision("base_net_amount"))
				+ flt(item.landed_cost_voucher_amount)
				+ flt(item.rm_supp_cost)
				+ flt(item.item_tax_amount)
				+ flt(item.amount_difference_with_purchase_invoice)
			)

			divisional_loss = flt(
				valuation_amount_as_per_doc - flt(stock_value_diff), item.precision("base_net_amount")
			)

			if divisional_loss:
				loss_account = (
					self.get_company_default("default_expense_account", ignore_validation=True)
					or stock_asset_rbnb
				)

				cost_center = item.cost_center or frappe.get_cached_value(
					"Company", self.company, "cost_center"
				)
				account_currency = get_account_currency(loss_account)
				self.add_gl_entry(
					gl_entries=gl_entries,
					account=loss_account,
					cost_center=cost_center,
					debit=divisional_loss,
					credit=0.0,
					remarks=remarks,
					against_account=stock_asset_account_name,
					account_currency=account_currency,
					project=item.project,
					item=item,
				)

		stock_items = self.get_stock_items()

		for d in self.get("items"):
			if (
				provisional_accounting_for_non_stock_items
				and d.item_code not in stock_items
				and flt(d.qty)
				and d.get("provisional_expense_account")
				and not d.is_fixed_asset
			):
				self.add_provisional_gl_entry(
					d, gl_entries, self.posting_date, d.get("provisional_expense_account")
				)
			elif flt(d.qty) and (flt(d.valuation_rate)):
				remarks = self.get("remarks") or _("Accounting Entry for {0}").format(
					"Asset" if d.is_fixed_asset else "Stock"
				)

				if not (
					(erpnext.is_perpetual_inventory_enabled(self.company) and d.item_code in stock_items)
					or (d.is_fixed_asset and not d.purchase_invoice)
				):
					continue

				stock_asset_rbnb = (
					self.get_company_default("asset_received_but_not_billed")
					if d.is_fixed_asset
					else self.get_company_default("stock_received_but_not_billed")
				)

				if d.is_fixed_asset:
					account_type = (
						"capital_work_in_progress_account"
						if is_cwip_accounting_enabled(d.asset_category)
						else "fixed_asset_account"
					)

					stock_asset_account_name = get_asset_account(
						account_type, asset_category=d.asset_category, company=self.company
					)

					stock_value_diff = (
						flt(d.base_net_amount) + flt(d.item_tax_amount) + flt(d.landed_cost_voucher_amount)
					)

				if (flt(d.valuation_rate) or d.is_fixed_asset) and flt(d.qty):
					make_item_asset_inward_gl_entry(d, stock_value_diff, stock_asset_account_name)
					outgoing_amount = make_stock_received_but_not_billed_entry(d)
					make_amount_difference_entry(d)
					make_divisional_loss_gl_entry(d, outgoing_amount)

			if d.is_fixed_asset and d.landed_cost_voucher_amount:
				self.update_assets(d, d.valuation_rate)

	def add_provisional_gl_entry(
		self, item, gl_entries, posting_date, provisional_account, reverse=0, item_amount=None
	):
		credit_currency = get_account_currency(provisional_account)
		expense_account = item.expense_account
		debit_currency = get_account_currency(item.expense_account)
		remarks = self.get("remarks") or _("Accounting Entry for Service")
		multiplication_factor = 1
		amount = item.base_amount

		if reverse:
			multiplication_factor = -1
			# Post reverse entry for previously posted amount
			amount = item_amount
			expense_account = frappe.db.get_value(
				"BAPP Item", {"name": item.get("bapp_detail")}, ["expense_account"]
			)

		self.add_gl_entry(
			gl_entries=gl_entries,
			account=provisional_account,
			cost_center=item.cost_center,
			debit=0.0,
			credit=multiplication_factor * amount,
			remarks=remarks,
			against_account=expense_account,
			account_currency=credit_currency,
			project=item.project,
			voucher_detail_no=item.name,
			item=item,
			posting_date=posting_date,
		)

		self.add_gl_entry(
			gl_entries=gl_entries,
			account=expense_account,
			cost_center=item.cost_center,
			debit=multiplication_factor * amount,
			credit=0.0,
			remarks=remarks,
			against_account=provisional_account,
			account_currency=debit_currency,
			project=item.project,
			voucher_detail_no=item.name,
			item=item,
			posting_date=posting_date,
		)

	def is_landed_cost_booked_for_any_item(self) -> bool:
		for x in self.items:
			if x.landed_cost_voucher_amount != 0:
				return True

		return False

	def make_tax_gl_entries(self, gl_entries, via_landed_cost_voucher=False):
		negative_expense_to_be_booked = sum([flt(d.item_tax_amount) for d in self.get("items")])
		# Cost center-wise amount breakup for other charges included for valuation
		valuation_tax = {}
		for tax in self.get("taxes"):
			if tax.category in ("Valuation", "Valuation and Total") and flt(
				tax.base_tax_amount_after_discount_amount
			):
				if not tax.cost_center:
					frappe.throw(
						_("Cost Center is required in row {0} in Taxes table for type {1}").format(
							tax.idx, _(tax.category)
						)
					)
				valuation_tax.setdefault(tax.name, 0)
				valuation_tax[tax.name] += (tax.add_deduct_tax == "Add" and 1 or -1) * flt(
					tax.base_tax_amount_after_discount_amount
				)

		if negative_expense_to_be_booked and valuation_tax:
			# Backward compatibility:
			# and charges added via Landed Cost Voucher,
			# post valuation related charges on "Stock Received But Not Billed"
			against_account = ", ".join([d.account for d in gl_entries if flt(d.debit) > 0])
			total_valuation_amount = sum(valuation_tax.values())
			amount_including_divisional_loss = negative_expense_to_be_booked
			i = 1
			for tax in self.get("taxes"):
				if valuation_tax.get(tax.name):
					account = tax.account_head
					if i == len(valuation_tax):
						applicable_amount = amount_including_divisional_loss
					else:
						applicable_amount = negative_expense_to_be_booked * (
							valuation_tax[tax.name] / total_valuation_amount
						)
						amount_including_divisional_loss -= applicable_amount

					self.add_gl_entry(
						gl_entries=gl_entries,
						account=account,
						cost_center=tax.cost_center,
						debit=0.0,
						credit=applicable_amount,
						remarks=self.remarks or _("Accounting Entry for Stock"),
						against_account=against_account,
						item=tax,
					)

					i += 1

	def update_assets(self, item, valuation_rate):
		assets = frappe.db.get_all(
			"Asset",
			filters={
				"bapp": self.name,
				"item_code": item.item_code,
				"bapp_item": ("in", [item.name, ""]),
			},
			fields=["name", "asset_quantity"],
		)

		for asset in assets:
			purchase_amount = flt(valuation_rate) * asset.asset_quantity
			frappe.db.set_value(
				"Asset",
				asset.name,
				{
					"gross_purchase_amount": purchase_amount,
					"purchase_amount": purchase_amount,
				},
			)

	def update_status(self, status):
		self.set_status(update=True, status=status)
		self.notify_update()
		clear_doctype_notifications(self)

	def update_billing_status(self, update_modified=True):
		updated_pr = [self.name]
		proposal_details = []
		for d in self.get("items"):
			if d.get("purchase_invoice") and d.get("purchase_invoice_item"):
				d.db_set("billed_amt", d.amount, update_modified=update_modified)
			elif d.proposal_item:
				proposal_details.append(d.proposal_item)

		if proposal_details:
			updated_pr += update_billed_amount_based_on_proposal(proposal_details, update_modified, self)

		for pr in set(updated_pr):
			pr_doc = self if (pr == self.name) else frappe.get_doc("BAPP", pr)
			update_billing_percentage(pr_doc, update_modified=update_modified)

def update_billed_amount_based_on_proposal(proposal_details, update_modified=True, pr_doc=None):
	po_billed_amt_details = get_billed_amount_against_po(proposal_details)

	# Get all BAPP Item rows against the Proposal Items
	bapp_details = get_bapp_against_proposal_details(proposal_details)

	pr_items = [bapp_detail.name for bapp_detail in bapp_details]
	pr_items_billed_amount = get_billed_amount_against_pr(pr_items)

	updated_pr = []
	for pr_item in bapp_details:
		billed_against_po = flt(po_billed_amt_details.get(pr_item.proposal_item))

		# Get billed amount directly against BAPP
		billed_amt_agianst_pr = flt(pr_items_billed_amount.get(pr_item.name, 0))

		# Distribute billed amount directly against PO between PRs based on FIFO
		if billed_against_po and billed_amt_agianst_pr < pr_item.amount:
			pending_to_bill = flt(pr_item.amount) - billed_amt_agianst_pr
			if pending_to_bill <= billed_against_po:
				billed_amt_agianst_pr += pending_to_bill
				billed_against_po -= pending_to_bill
			else:
				billed_amt_agianst_pr += billed_against_po
				billed_against_po = 0

		po_billed_amt_details[pr_item.proposal_item] = billed_against_po

		if pr_item.billed_amt != billed_amt_agianst_pr:
			# update existing doc if possible
			if pr_doc and pr_item.parent == pr_doc.name:
				pr_item = next((item for item in pr_doc.items if item.name == pr_item.name), None)
				pr_item.db_set("billed_amt", billed_amt_agianst_pr, update_modified=update_modified)

			else:
				frappe.db.set_value(
					"BAPP Item",
					pr_item.name,
					"billed_amt",
					billed_amt_agianst_pr,
					update_modified=update_modified,
				)

			updated_pr.append(pr_item.parent)

	return updated_pr


def get_bapp_against_proposal_details(proposal_details):
	# Get BAPPs against Proposal Items

	bapp = frappe.qb.DocType("BAPP")
	bapp_item = frappe.qb.DocType("BAPP Item")

	query = (
		frappe.qb.from_(bapp)
		.inner_join(bapp_item)
		.on(bapp.name == bapp_item.parent)
		.select(
			bapp_item.name,
			bapp_item.parent,
			bapp_item.amount,
			bapp_item.billed_amt,
			bapp_item.proposal_item,
		)
		.where(
			(bapp_item.proposal_item.isin(proposal_details))
			& (bapp.docstatus == 1)
		)
		.orderby(CombineDatetime(bapp.posting_date, bapp.posting_time))
		.orderby(bapp.name)
	)

	return query.run(as_dict=True)


def get_billed_amount_against_pr(pr_items):
	# Get billed amount directly against Purchase Receipt

	if not pr_items:
		return {}

	purchase_invoice_item = frappe.qb.DocType("Purchase Invoice Item")

	query = (
		frappe.qb.from_(purchase_invoice_item)
		.select(fn.Sum(purchase_invoice_item.amount).as_("billed_amt"), purchase_invoice_item.bapp_detail)
		.where((purchase_invoice_item.bapp_detail.isin(pr_items)) & (purchase_invoice_item.docstatus == 1))
		.groupby(purchase_invoice_item.bapp_detail)
	).run(as_dict=1)

	return {d.bapp_detail: flt(d.billed_amt) for d in query}


def get_billed_amount_against_po(po_items):
	# Get billed amount directly against Proposal
	if not po_items:
		return {}

	purchase_invoice = frappe.qb.DocType("Purchase Invoice")
	purchase_invoice_item = frappe.qb.DocType("Purchase Invoice Item")

	query = (
		frappe.qb.from_(purchase_invoice_item)
		.inner_join(purchase_invoice)
		.on(purchase_invoice_item.parent == purchase_invoice.name)
		.select(fn.Sum(purchase_invoice_item.amount).as_("billed_amt"), purchase_invoice_item.proposal_detail)
		.where(
			(purchase_invoice_item.proposal_detail.isin(po_items))
			& (purchase_invoice.docstatus == 1)
			& (purchase_invoice_item.bapp_detail.isnull())
			& (purchase_invoice.update_stock == 0)
		)
		.groupby(purchase_invoice_item.proposal_detail)
	).run(as_dict=1)

	return {d.proposal_detail: flt(d.billed_amt) for d in query}


def update_billing_percentage(pr_doc, update_modified=True):
	# Update Billing % based on pending accepted qty
	buying_settings = frappe.get_single("Buying Settings")
	over_billing_allowance = frappe.db.get_single_value("Accounts Settings", "over_billing_allowance")

	total_amount, total_billed_amount = 0, 0

	for item in pr_doc.items:
		pending_amount = flt(item.amount)
		if buying_settings.bill_for_rejected_quantity_in_purchase_invoice:
			pending_amount = flt(item.amount)

		total_billable_amount = abs(flt(item.amount))
		if pending_amount > 0:
			total_billable_amount = pending_amount if item.billed_amt <= pending_amount else item.billed_amt

		total_amount += total_billable_amount
		total_billed_amount += abs(flt(item.billed_amt))

		amount = item.amount
		
		if amount and item.billed_amt > amount:
			per_over_billed = (flt(item.billed_amt / amount, 2) * 100) - 100
			if per_over_billed > over_billing_allowance:
				frappe.throw(
					_("Over Billing Allowance exceeded for BAPP Item {0} ({1}) by {2}%").format(
						item.name, frappe.bold(item.item_code), per_over_billed - over_billing_allowance
					)
				)

	percent_billed = round(100 * (total_billed_amount / (total_amount or 1)), 6)
	pr_doc.db_set("per_billed", percent_billed)

	if update_modified:
		pr_doc.set_status(update=True)
		pr_doc.notify_update()

@frappe.whitelist()
def make_purchase_invoice(source_name, target_doc=None, args=None):
	from erpnext.accounts.party import get_payment_terms_template

	doc = frappe.get_doc("BAPP", source_name)
	invoiced_qty_map = get_invoiced_qty_map(source_name)

	def set_missing_values(source, target):
		if len(target.get("items")) == 0:
			frappe.throw(_("All items have already been Invoiced/Returned"))
		
		doc = frappe.get_doc(target)
		doc.invoice_type = "SPK"
		doc.payment_terms_template = get_payment_terms_template(source.supplier, "Supplier", source.company)
		doc.run_method("onload")
		doc.run_method("set_missing_values")

		doc.ppn = []
		if source.ppn:
			doc.append("ppn", {
				"type": source.ppn,
				"account": source.ppn_account,
				"percentage": source.ppn_rate
			})
			
		if args and args.get("merge_taxes"):
			merge_taxes(source.get("taxes") or [], doc)

		doc.run_method("calculate_taxes_and_totals")
		doc.set_payment_schedule()

	def update_item(source_doc, target_doc, source_parent):
		target_doc.qty = get_pending_qty(source_doc)
		target_doc.stock_qty = flt(target_doc.qty) * flt(
			target_doc.conversion_factor, target_doc.precision("conversion_factor")
		)

	def get_pending_qty(item_row):
		return item_row.qty - invoiced_qty_map.get(item_row.name, 0)

	doclist = get_mapped_doc(
		"BAPP",
		source_name,
		{
			"BAPP": {
				"doctype": "Purchase Invoice",
				"field_map": {
					"bill_date": "bill_date",
					"is_cwip": "cwip_asset",
					"asset_category": "asset_category",
					"retensi": "retensi"
				},
				"validation": {
					"docstatus": ["=", 1],
				},
			},
			"BAPP Item": {
				"doctype": "Purchase Invoice Item",
				"field_map": {
					"name": "bapp_detail",
					"parent": "bapp",
					"qty": "received_qty",
					"proposal_item": "proposal_detail",
					"proposal": "proposal",
					"is_fixed_asset": "is_fixed_asset",
					"asset_location": "asset_location",
					"asset_category": "asset_category",
					"wip_composite_asset": "wip_composite_asset",
				},
				"postprocess": update_item,
				"filter": lambda d: get_pending_qty(d) <= 0,
			},
			"Purchase Taxes and Charges": {
				"doctype": "Purchase Taxes and Charges",
				"reset_value": not (args and args.get("merge_taxes")),
				"ignore": args.get("merge_taxes") if args else 0,
			},
		},
		target_doc,
		set_missing_values,
	)

	return doclist


def get_invoiced_qty_map(bapp):
	"""returns a map: {bapp_detail: invoiced_qty}"""
	invoiced_qty_map = {}

	for bapp_detail, qty in frappe.db.sql(
		"""select bapp_detail, qty from `tabPurchase Invoice Item`
		where bapp=%s and docstatus=1""",
		bapp,
	):
		if not invoiced_qty_map.get(bapp_detail):
			invoiced_qty_map[bapp_detail] = 0
		invoiced_qty_map[bapp_detail] += qty

	return invoiced_qty_map

@frappe.whitelist()
def update_bapp_status(docname, status):
	pr = frappe.get_doc("BAPP", docname)
	pr.update_status(status)

@erpnext.allow_regional
def update_regional_gl_entries(gl_list, doc):
	return
