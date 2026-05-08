# Copyright (c) 2026, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import json

import frappe
from frappe.utils import cint, flt

from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt

class SthPurchaseReceipt(PurchaseReceipt):

	def update_valuation_rate_custom(self, reset_outgoing_rate=True):
		"""
		item_tax_amount is the total tax amount applied on that item
		stored for valuation

		TODO: rename item_tax_amount to valuation_tax_amount
		"""
		stock_and_asset_items = []
		stock_and_asset_items = self.get_stock_items() + self.get_asset_items()

		stock_and_asset_items_qty, stock_and_asset_items_amount = 0, 0
		last_item_idx = 1
		for d in self.get("items"):
			if d.item_code and d.item_code in stock_and_asset_items:
				stock_and_asset_items_qty += flt(d.qty)
				stock_and_asset_items_amount += flt(d.base_net_amount)
				last_item_idx = d.idx

		total_valuation_amount = sum(
			flt(d.base_tax_amount_after_discount_amount)
			for d in self.get("taxes")
			if d.category in ["Valuation", "Valuation and Total"]
		)

		valuation_amount_adjustment = total_valuation_amount
		for i, item in enumerate(self.get("items")):
			if item.item_code and item.qty and item.item_code in stock_and_asset_items:
				item_proportion = (
					flt(item.base_net_amount) / stock_and_asset_items_amount
					if stock_and_asset_items_amount
					else flt(item.qty) / stock_and_asset_items_qty
				)

				if i == (last_item_idx - 1):
					item.item_tax_amount = flt(
						valuation_amount_adjustment, self.precision("item_tax_amount", item)
					)
				else:
					item.item_tax_amount = flt(
						item_proportion * total_valuation_amount, self.precision("item_tax_amount", item)
					)
					valuation_amount_adjustment -= item.item_tax_amount

				self.round_floats_in(item)
				if flt(item.conversion_factor) == 0.0:
					item.conversion_factor = (
						get_conversion_factor(item.item_code, item.uom).get("conversion_factor") or 1.0
					)

				net_rate = item.base_net_amount
				if item.sales_incoming_rate:  # for internal transfer
					net_rate = item.qty * item.sales_incoming_rate

				qty_in_stock_uom = flt(item.qty * item.conversion_factor)
				if self.get("is_old_subcontracting_flow"):
					item.rm_supp_cost = self.get_supplied_items_cost(item.name, reset_outgoing_rate)
					item.valuation_rate = (
						net_rate
						+ item.item_tax_amount
						+ item.rm_supp_cost
						+ flt(item.landed_cost_voucher_amount)
					) / qty_in_stock_uom
				else:
					item.valuation_rate = (
						net_rate
						+ item.item_tax_amount
						+ flt(item.landed_cost_voucher_amount)
						+ flt(item.get("amount_difference_with_purchase_invoice"))
					) / qty_in_stock_uom
			else:
				item.valuation_rate = 0.0

	def update_stock_ledger(self, allow_negative_stock=False, via_landed_cost_voucher=False):
		self.update_ordered_and_reserved_qty()

		sl_entries = []
		stock_items = self.get_stock_items()

		self.update_valuation_rate_custom()

		for d in self.get("items"):
			if d.item_code not in stock_items:
				continue

			if d.warehouse:
				pr_qty = flt(flt(d.qty) * flt(d.conversion_factor), d.precision("stock_qty"))

				if pr_qty:
					if d.from_warehouse and (
						(not cint(self.is_return) and self.docstatus == 1)
						or (cint(self.is_return) and self.docstatus == 2)
					):
						serial_and_batch_bundle = d.get("serial_and_batch_bundle")
						if self.is_internal_transfer() and self.is_return and self.docstatus == 2:
							serial_and_batch_bundle = frappe.db.get_value(
								"Stock Ledger Entry",
								{"voucher_detail_no": d.name, "warehouse": d.from_warehouse},
								"serial_and_batch_bundle",
							)

						from_warehouse_sle = self.get_sl_entries(
							d,
							{
								"actual_qty": -1 * pr_qty,
								"warehouse": d.from_warehouse,
								"outgoing_rate": d.rate,
								"recalculate_rate": 1,
								"dependant_sle_voucher_detail_no": d.name,
								"serial_and_batch_bundle": serial_and_batch_bundle,
							},
						)

						sl_entries.append(from_warehouse_sle)

					type_of_transaction = "Inward"
					if self.docstatus == 2:
						type_of_transaction = "Outward"

					sle = self.get_sl_entries(
						d,
						{
							"actual_qty": flt(pr_qty),
							"serial_and_batch_bundle": (
								d.serial_and_batch_bundle
								if not self.is_internal_transfer()
								or self.is_return
								or (self.is_internal_transfer() and self.docstatus == 2)
								else self.get_package_for_target_warehouse(
									d, type_of_transaction=type_of_transaction
								)
							),
						},
					)

					if self.is_return:
						outgoing_rate = get_rate_for_return(
							self.doctype, self.name, d.item_code, self.return_against, item_row=d
						)

						sle.update(
							{
								"outgoing_rate": outgoing_rate,
								"recalculate_rate": 1,
								"serial_and_batch_bundle": d.serial_and_batch_bundle,
							}
						)
						if d.from_warehouse:
							sle.dependant_sle_voucher_detail_no = d.name
					else:
						sle.update(
							{
								"incoming_rate": d.valuation_rate,
								"recalculate_rate": 1
								if (self.is_subcontracted and (d.bom or d.get("fg_item"))) or d.from_warehouse
								else 0,
							}
						)
					sl_entries.append(sle)

					if d.from_warehouse and (
						(not cint(self.is_return) and self.docstatus == 2)
						or (cint(self.is_return) and self.docstatus == 1)
					):
						serial_and_batch_bundle = None
						if self.is_internal_transfer() and self.docstatus == 2:
							serial_and_batch_bundle = frappe.db.get_value(
								"Stock Ledger Entry",
								{"voucher_detail_no": d.name, "warehouse": d.warehouse},
								"serial_and_batch_bundle",
							)

						from_warehouse_sle = self.get_sl_entries(
							d,
							{
								"actual_qty": -1 * pr_qty,
								"warehouse": d.from_warehouse,
								"recalculate_rate": 1,
								"serial_and_batch_bundle": (
									self.get_package_for_target_warehouse(d, d.from_warehouse, "Inward")
									if self.is_internal_transfer() and self.is_return
									else serial_and_batch_bundle
								),
							},
						)

						sl_entries.append(from_warehouse_sle)

			if flt(d.rejected_qty) != 0:
				valuation_rate_for_rejected_item = 0.0
				if frappe.db.get_single_value("Buying Settings", "set_valuation_rate_for_rejected_materials"):
					valuation_rate_for_rejected_item = d.valuation_rate

				sl_entries.append(
					self.get_sl_entries(
						d,
						{
							"warehouse": d.rejected_warehouse,
							"actual_qty": flt(
								flt(d.rejected_qty) * flt(d.conversion_factor), d.precision("stock_qty")
							),
							"incoming_rate": valuation_rate_for_rejected_item if not self.is_return else 0.0,
							"outgoing_rate": valuation_rate_for_rejected_item if self.is_return else 0.0,
							"serial_and_batch_bundle": d.rejected_serial_and_batch_bundle,
						},
					)
				)

		if self.get("is_old_subcontracting_flow"):
			self.make_sl_entries_for_supplier_warehouse(sl_entries)

		self.make_sl_entries(
			sl_entries,
			allow_negative_stock=allow_negative_stock,
			via_landed_cost_voucher=via_landed_cost_voucher,
		)