# Copyright (c) 2026, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import json

import frappe
from frappe import _, throw
from frappe.query_builder.functions import Sum
from frappe.utils import cint, flt, get_link_to_form

from erpnext.accounts.doctype.purchase_invoice.purchase_invoice import PurchaseInvoice

from erpnext.stock.doctype.purchase_receipt.purchase_receipt import (
	update_billed_amount_based_on_po,
)

from sth.legal.doctype.bapp.bapp import (
	update_billed_amount_based_on_proposal,
)

class SthPurchaseInvoice(PurchaseInvoice):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.status_updater = [
			{
				"source_dt": "Purchase Invoice Item",
				"target_dt": "Proposal Item",
				"join_field": "proposal_detail",
				"target_field": "billed_amt",
				"target_parent_dt": "Proposal",
				"target_parent_field": "per_billed",
				"target_ref_field": "amount",
				"source_field": "amount",
				"percent_join_field": "propsal",
				"overflow_type": "billing",
			}
		]

	def validate(self):
		update_cwip_expense_accounts(self)
		super().validate()


	def validate_with_previous_doc(self):
		super(PurchaseInvoice, self).validate_with_previous_doc(
			{
				"Purchase Order": {
					"ref_dn_field": "purchase_order",
					"compare_fields": [["supplier", "="], ["company", "="], ["currency", "="]],
				},
				"Purchase Order Item": {
					"ref_dn_field": "po_detail",
					"compare_fields": [["project", "="], ["item_code", "="], ["uom", "="]],
					"is_child_table": True,
					"allow_duplicate_prev_row_id": True,
				},
				"Purchase Receipt": {
					"ref_dn_field": "purchase_receipt",
					"compare_fields": [["supplier", "="], ["company", "="], ["currency", "="]],
				},
				"Purchase Receipt Item": {
					"ref_dn_field": "pr_detail",
					"compare_fields": [["project", "="], ["item_code", "="], ["uom", "="]],
					"is_child_table": True,
				},
				"Proposal": {
					"ref_dn_field": "proposal",
					"compare_fields": [["supplier", "="], ["company", "="], ["currency", "="]],
				},
				"Proposal Item": {
					"ref_dn_field": "proposal_detail",
					"compare_fields": [["project", "="], ["item_code", "="], ["kegiatan", "="], ["kegiatan_name", "="], ["uom", "="]],
					"is_child_table": True,
					"allow_duplicate_prev_row_id": True,
				},
				"BAPP": {
					"ref_dn_field": "bapp",
					"compare_fields": [["supplier", "="], ["company", "="], ["currency", "="]],
				},
				"BAPP Item": {
					"ref_dn_field": "bapp_detail",
					"compare_fields": [["project", "="], ["item_code", "="], ["kegiatan", "="], ["kegiatan_name", "="], ["uom", "="]],
					"is_child_table": True,
				},
			}
		)

		if (
			cint(frappe.db.get_single_value("Buying Settings", "maintain_same_rate"))
			and not self.is_return
			and not self.is_internal_supplier
		):
			self.validate_rate_with_reference_doc(
				[
					["Purchase Order", "purchase_order", "po_detail"],
					["Purchase Receipt", "purchase_receipt", "pr_detail"],
					["Proposal", "proposal", "proposal_detail"],
					["BAPP", "bapp", "bapp_detail"],
				]
			)
	
	def po_required(self):
		if frappe.db.get_value("Buying Settings", None, "po_required") == "Yes":
			if frappe.get_value(
				"Supplier", self.supplier, "allow_purchase_invoice_creation_without_purchase_order"
			):
				return

			for d in self.get("items"):
				if not (d.purchase_order or d.proposal):
					msg = _("Purchase Order Required for item {}").format(frappe.bold(d.item_code))
					msg += "<br><br>"
					msg += _(
						"To submit the invoice without purchase order please set {0} as {1} in {2}"
					).format(
						frappe.bold(_("Purchase Order Required")),
						frappe.bold(_("No")),
						get_link_to_form("Buying Settings", "Buying Settings", "Buying Settings"),
					)
					throw(msg, title=_("Mandatory Purchase Order"))
						 
	def pr_required(self):
		stock_items = self.get_stock_items()
		if frappe.db.get_value("Buying Settings", None, "pr_required") == "Yes":
			if frappe.get_value(
				"Supplier", self.supplier, "allow_purchase_invoice_creation_without_purchase_receipt"
			):
				return

			for d in self.get("items"):
				if not (d.purchase_receipt or d.bapp) and d.item_code in stock_items:
					msg = _("Purchase Receipt Required for item {}").format(frappe.bold(d.item_code))
					msg += "<br><br>"
					msg += _(
						"To submit the invoice without purchase receipt please set {0} as {1} in {2}"
					).format(
						frappe.bold(_("Purchase Receipt Required")),
						frappe.bold(_("No")),
						get_link_to_form("Buying Settings", "Buying Settings", "Buying Settings"),
					)
					throw(msg, title=_("Mandatory Purchase Receipt"))

	def check_prev_docstatus(self):
		for d in self.get("items"):
			if d.purchase_order:
				submitted = frappe.db.sql(
					"select name from `tabPurchase Order` where docstatus = 1 and name = %s", d.purchase_order
				)
				if not submitted:
					frappe.throw(_("Purchase Order {0} is not submitted").format(d.purchase_order))
			if d.purchase_receipt:
				submitted = frappe.db.sql(
					"select name from `tabPurchase Receipt` where docstatus = 1 and name = %s",
					d.purchase_receipt,
				)
				if not submitted:
					frappe.throw(_("Purchase Receipt {0} is not submitted").format(d.purchase_receipt))

			if d.proposal:
				submitted = frappe.db.sql(
					"select name from `tabProposal` where docstatus = 1 and name = %s",
					d.proposal,
				)
				if not submitted:
					frappe.throw(_("Proposal {0} is not submitted").format(d.proposal))

			if d.bapp:
				submitted = frappe.db.sql(
					"select name from `tabBAPP` where docstatus = 1 and name = %s",
					d.bapp,
				)
				if not submitted:
					frappe.throw(_("BAPP {0} is not submitted").format(d.bapp))   
	
	def update_billing_status_in_pr(self, update_modified=True):
		if self.is_return and not self.update_billed_amount_in_purchase_receipt:
			return

		updated_pr = []
		po_details = []
		updated_bapp = []
		proposal_details = []

		pr_details_billed_amt = self.get_pr_details_billed_amt()
		bapp_details_billed_amt = self.get_bapp_details_billed_amt()

		for d in self.get("items"):
			if d.pr_detail:
				frappe.db.set_value(
					"Purchase Receipt Item",
					d.pr_detail,
					"billed_amt",
					flt(pr_details_billed_amt.get(d.pr_detail)),
					update_modified=update_modified,
				)
				updated_pr.append(d.purchase_receipt)
			elif d.bapp_detail:
				frappe.db.set_value(
					"BAPP Item",
					d.bapp_detail,
					"billed_amt",
					flt(bapp_details_billed_amt.get(d.bapp_detail)),
					update_modified=update_modified,
				)
				updated_bapp.append(d.bapp)
			elif d.po_detail:
				po_details.append(d.po_detail)
			elif d.proposal_detail:
				proposal_details.append(d.proposal_detail)

		if po_details:
			updated_pr += update_billed_amount_based_on_po(po_details, update_modified)

		if proposal_details:
			updated_bapp += update_billed_amount_based_on_proposal(proposal_details, update_modified)

		adjust_incoming_rate = frappe.db.get_single_value(
			"Buying Settings", "set_landed_cost_based_on_purchase_invoice_rate"
		)

		for pr in set(updated_pr):
			from erpnext.stock.doctype.purchase_receipt.purchase_receipt import update_billing_percentage

			pr_doc = frappe.get_doc("Purchase Receipt", pr)
			update_billing_percentage(
				pr_doc, update_modified=update_modified, adjust_incoming_rate=adjust_incoming_rate
			)

		for bapp in set(updated_bapp):
			from sth.legal.doctype.bapp.bapp import update_billing_percentage

			bapp_doc = frappe.get_doc("BAPP", bapp)
			update_billing_percentage(
				bapp_doc, update_modified=update_modified
			)

	def get_bapp_details_billed_amt(self):
		# Get billed amount based on purchase receipt item reference (pr_detail) in purchase invoice

		bapp_details_billed_amt = {}
		bapp_details = [d.get("bapp_detail") for d in self.get("items") if d.get("bapp_detail")]
		if bapp_details:
			doctype = frappe.qb.DocType("Purchase Invoice Item")
			query = (
				frappe.qb.from_(doctype)
				.select(doctype.bapp_detail, Sum(doctype.amount))
				.where(doctype.bapp_detail.isin(bapp_details) & doctype.docstatus == 1)
				.groupby(doctype.bapp_detail)
			)

			bapp_details_billed_amt = frappe._dict(query.run(as_list=1))

		return bapp_details_billed_amt
			  
@frappe.whitelist()
def get_all_training_event_by_supplier(supplier):
  events = frappe.get_all(
	"Training Event",
	filters={
	  "supplier": supplier,
	  "docstatus": 1,
	  "custom_purchase_invoice": ["is", "not set"],
	},
	fields=[
	  "name",
	  "custom_posting_date",
	  "supplier",
	],
	order_by="custom_posting_date desc"
  )

  return events

@frappe.whitelist()
def get_item_costing_in_training_events(training_events):
  training_events = frappe.parse_json(training_events)
  return frappe.db.sql("""
	SELECT
	tec.parent,
	tec.name,
	tec.expense_type,
	i.name as item,
	i.item_name as item_code,
	i.stock_uom as stock_uom,
	tec.total_amount
	FROM `tabTraining Event Costing` as tec
	JOIN `tabExpense Claim Type` as ect ON ect.name = tec.expense_type
	JOIN `tabItem` as i ON i.name = ect.custom_item
	WHERE tec.parent IN %(training_events)s;
  """, {"training_events": tuple(training_events)}, as_dict=True)


def update_cwip_expense_accounts(doc):
	if doc.cwip_asset and doc.asset_category:
		asset_category_doc = frappe.get_cached_doc('Asset Category', doc.asset_category)

		cwip_account = ""
		for row in asset_category_doc.accounts:
			if row.company_name == doc.company:
				if row.capital_work_in_progress_account:
					cwip_account = row.capital_work_in_progress_account
		
		if not cwip_account:
			frappe.throw(
				_('Capital Work in Progress Account is not set for Company {0}').format(doc.company),
				title=_('CWIP Account Missing')
			)

		for item in doc.items:
			item.expense_account = cwip_account