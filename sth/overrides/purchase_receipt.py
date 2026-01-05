# Copyright (c) 2026, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import json

import frappe
from frappe.utils import cint, flt

from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt

class SthPurchaseReceipt(PurchaseReceipt):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.status_updater.extend(
			[
				{
					"target_dt": "Proposal Item",
					"join_field": "proposal_item",
					"target_field": "received_qty",
					"target_parent_dt": "Proposal",
					"target_parent_field": "per_received",
					"target_ref_field": "qty",
					"source_dt": "Purchase Receipt Item",
					"source_field": "received_qty",
					"second_source_dt": "Purchase Invoice Item",
					"second_source_field": "received_qty",
					"second_join_field": "po_detail",
					"percent_join_field": "proposal",
					"overflow_type": "receipt",
					"second_source_extra_cond": """ and exists(select name from `tabPurchase Invoice`
					where name=`tabPurchase Invoice Item`.parent and update_stock = 1)""",
				},
			]
		)
	def validate_with_previous_doc(self):
		super(PurchaseReceipt, self).validate_with_previous_doc(
			{
				"Purchase Order": {
					"ref_dn_field": "purchase_order",
					"compare_fields": [["supplier", "="], ["company", "="], ["currency", "="]],
				},
				"Purchase Order Item": {
					"ref_dn_field": "purchase_order_item",
					"compare_fields": [["project", "="], ["uom", "="], ["item_code", "="]],
					"is_child_table": True,
					"allow_duplicate_prev_row_id": True,
				},
				"Proposal": {
					"ref_dn_field": "proposal",
					"compare_fields": [["supplier", "="], ["company", "="], ["currency", "="]],
				},
				"Proposal Item": {
					"ref_dn_field": "proposal_item",
					"compare_fields": [["project", "="], ["uom", "="], ["item_code", "="]],
					"is_child_table": True,
					"allow_duplicate_prev_row_id": True,
				},
			}
		)

		if (
			cint(frappe.db.get_single_value("Buying Settings", "maintain_same_rate"))
			and not self.is_return
			and not self.is_internal_supplier
		):
			self.validate_rate_with_reference_doc(
				[["Purchase Order", "purchase_order", "purchase_order_item"]]
			)