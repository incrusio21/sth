# Copyright (c) 2026, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import json

import frappe
from frappe.utils import cint, flt
from frappe import _, bold

from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt
from erpnext.accounts.general_ledger import (
	make_gl_entries,
	make_reverse_gl_entries,
	process_gl_map,
)
from erpnext.controllers.sales_and_purchase_return import get_rate_for_return
from erpnext.controllers.accounts_controller import merge_taxes
from frappe.model.mapper import get_mapped_doc
from sth.custom import method_ambil_account

class SthPurchaseReceipt(PurchaseReceipt):

	def on_submit(self):
		super().on_submit()
		make_gl_entries_for_non_stock_items(self)

	def on_cancel(self):
		super().on_cancel()
		make_gl_entries_for_non_stock_items(self, cancel=True)

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
				enabled_companies = get_enabled_companies()
				if self.get("is_old_subcontracting_flow"):
					item.rm_supp_cost = self.get_supplied_items_cost(item.name, reset_outgoing_rate)
					
					if self.company not in enabled_companies:
						item.valuation_rate = (
							net_rate
							+ item.item_tax_amount
							+ item.rm_supp_cost
							+ flt(item.landed_cost_voucher_amount)
							- self.pph_22
						) / qty_in_stock_uom
					else:
						item.valuation_rate = (
							net_rate
							+ item.item_tax_amount
							+ item.rm_supp_cost
							+ flt(item.landed_cost_voucher_amount)
						) / qty_in_stock_uom
				else:
					if self.company not in enabled_companies:
						item.valuation_rate = (
							net_rate
							+ item.item_tax_amount
							+ flt(item.landed_cost_voucher_amount)
							+ flt(item.get("amount_difference_with_purchase_invoice"))
							- self.pph_22
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

	def get_gl_entries(self, warehouse_account=None, default_expense_account=None, default_cost_center=None):
		if not warehouse_account:
			warehouse_account = get_warehouse_account_map(self.company)

		sle_map = self.get_stock_ledger_details()
		voucher_details = self.get_voucher_details(default_expense_account, default_cost_center, sle_map)

		gl_list = []
		warehouse_with_no_account = []
		precision = self.get_debit_field_precision()
		for item_row in voucher_details:
			sle_list = sle_map.get(item_row.name)
			sle_rounding_diff = 0.0
			if sle_list:
				for sle in sle_list:
					if warehouse_account.get(sle.warehouse):
						# from warehouse account

						sle_rounding_diff += flt(sle.stock_value_difference)

						# self.check_expense_account(item_row)
						company_doc = frappe.get_doc("Company", self.company)
						# expense account/ target_warehouse / source_warehouse
						# if item_row.get("target_warehouse"):
						# 	warehouse = item_row.get("target_warehouse")
						# 	expense_account = warehouse_account[warehouse]["account"]
						# else:
						# 	expense_account = item_row.expense_account

						expense_account = company_doc.stock_adjustment_account

						enabled_companies = get_enabled_companies()

						service = 0
						if self.sub_purchase_type == "Service Request":
							service = 1


						if self.company in enabled_companies:
							expense_account = ""
							if service == 1:
								expense_account = method_ambil_account.ambil_ap_in_transit_procurement("jasa", self.company)
							else:
								expense_account = method_ambil_account.ambil_ap_in_transit_procurement("barang", self.company)

							gl_list.append(
								self.get_gl_dict(
									{
										"account": warehouse_account[sle.warehouse]["account"],
										"against": expense_account,
										"cost_center": item_row.cost_center,
										"project": sle.get("project") or item_row.project or self.get("project"),
										"remarks": self.get("remarks") or _("Accounting Entry for Stock"),
										"debit": flt(sle.stock_value_difference, precision),
										"is_opening": item_row.get("is_opening")
										or self.get("is_opening")
										or "No",
									},
									warehouse_account[sle.warehouse]["account_currency"],
									item=item_row,
								)
							)

							gl_list.append(
								self.get_gl_dict(
									{
										"account": expense_account,
										"against": warehouse_account[sle.warehouse]["account"],
										"cost_center": item_row.cost_center,
										"remarks": self.get("remarks") or _("Accounting Entry for Stock"),
										"debit": -1 * flt(sle.stock_value_difference, precision),
										"project": sle.get("project")
										or item_row.get("project")
										or self.get("project"),
										"is_opening": item_row.get("is_opening")
										or self.get("is_opening")
										or "No",
										"party": "",
										"party_type": ""
									},
									item=item_row,
								)
							)
						else:
							expense_account = ""
							if service == 1:
								expense_account = method_ambil_account.ambil_ap_in_transit_procurement("jasa", self.company)
							else:
								expense_account = method_ambil_account.ambil_ap_in_transit_procurement("barang", self.company)
							
							gl_list.append(
								self.get_gl_dict(
									{
										"account": warehouse_account[sle.warehouse]["account"],
										"against": expense_account,
										"cost_center": item_row.cost_center,
										"project": sle.get("project") or item_row.project or self.get("project"),
										"remarks": self.get("remarks") or _("Accounting Entry for Stock"),
										"debit": flt(sle.stock_value_difference, precision),
										"is_opening": item_row.get("is_opening")
										or self.get("is_opening")
										or "No",
									},
									warehouse_account[sle.warehouse]["account_currency"],
									item=item_row,
								)
							)

							for row in self.taxes:
								if "PPH 22" in row.account_head:
									expense_account_head = frappe.db.get_value(
										"Account",
										{"account_number": "1171001", "company": self.company},
										"name"
									)

							gl_list.append(
								self.get_gl_dict(
									{
										"account": expense_account_head,
										"against": expense_account,
										"cost_center": item_row.cost_center,
										"project": sle.get("project") or item_row.project or self.get("project"),
										"remarks": self.get("remarks") or _("Accounting Entry for Stock"),
										"debit": flt(self.pph_22, precision),
										"is_opening": item_row.get("is_opening")
										or self.get("is_opening")
										or "No",
									},
									warehouse_account[sle.warehouse]["account_currency"],
									item=item_row,
								)
							)

							gl_list.append(
								self.get_gl_dict(
									{
										"account": expense_account,
										"against": warehouse_account[sle.warehouse]["account"],
										"cost_center": item_row.cost_center,
										"remarks": self.get("remarks") or _("Accounting Entry for Stock"),
										"debit": -1 * flt(sle.stock_value_difference, precision),
										"project": sle.get("project")
										or item_row.get("project")
										or self.get("project"),
										"is_opening": item_row.get("is_opening")
										or self.get("is_opening")
										or "No",
										"party": "",
										"party_type": ""
									},
									item=item_row,
								)
							)

							gl_list.append(
								self.get_gl_dict(
									{
										"account": expense_account,
										"against": warehouse_account[sle.warehouse]["account"],
										"cost_center": item_row.cost_center,
										"remarks": self.get("remarks") or _("Accounting Entry for Stock"),
										"debit": -1 * flt(self.pph_22, precision),
										"project": sle.get("project")
										or item_row.get("project")
										or self.get("project"),
										"is_opening": item_row.get("is_opening")
										or self.get("is_opening")
										or "No",
									},
									item=item_row,
								)
							)
					elif sle.warehouse not in warehouse_with_no_account:
						warehouse_with_no_account.append(sle.warehouse)

			if abs(sle_rounding_diff) > (1.0 / (10**precision)) and self.is_internal_transfer():
				warehouse_asset_account = ""
				if self.get("is_internal_customer"):
					warehouse_asset_account = warehouse_account[item_row.get("target_warehouse")]["account"]
				elif self.get("is_internal_supplier"):
					warehouse_asset_account = warehouse_account[item_row.get("warehouse")]["account"]

				expense_account = frappe.get_cached_value("Company", self.company, "default_expense_account")
				if not expense_account:
					frappe.throw(
						_(
							"Please set default cost of goods sold account in company {0} for booking rounding gain and loss during stock transfer"
						).format(frappe.bold(self.company))
					)

				gl_list.append(
					self.get_gl_dict(
						{
							"account": expense_account,
							"against": warehouse_asset_account,
							"cost_center": item_row.cost_center,
							"project": item_row.project or self.get("project"),
							"remarks": _("Rounding gain/loss Entry for Stock Transfer"),
							"debit": sle_rounding_diff,
							"is_opening": item_row.get("is_opening") or self.get("is_opening") or "No",
						},
						warehouse_account[sle.warehouse]["account_currency"],
						item=item_row,
					)
				)

				gl_list.append(
					self.get_gl_dict(
						{
							"account": warehouse_asset_account,
							"against": expense_account,
							"cost_center": item_row.cost_center,
							"remarks": _("Rounding gain/loss Entry for Stock Transfer"),
							"credit": sle_rounding_diff,
							"project": item_row.get("project") or self.get("project"),
							"is_opening": item_row.get("is_opening") or self.get("is_opening") or "No",
						},
						item=item_row,
					)
				)

		if warehouse_with_no_account:
			for wh in warehouse_with_no_account:
				if frappe.get_cached_value("Warehouse", wh, "company"):
					frappe.throw(
						_(
							"Warehouse {0} is not linked to any account, please mention the account in the warehouse record or set default inventory account in company {1}."
						).format(wh, self.company)
					)
		
		return process_gl_map(gl_list, precision=precision)


def get_enabled_companies():
	try:
		settings = frappe.get_single("Procurement Valuation Rate Settings")
		return {
			row.company
			for row in settings.get("enabled_companies", [])
			if row.enabled
		}
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Procurement Valuation Rate Settings – fetch error")
		return set()

def make_gl_entries_for_non_stock_items(doc, cancel=False):
	"""
	Membuat GL Entry untuk Purchase Receipt dengan item non-stock.

	Debit  : Fixed Asset Account (dari Asset Category → Company Account)
	Credit : AP in Transit Account (dari Procurement Settings → ap_in_transit_po → account by company)

	Args:
		doc    : Purchase Receipt document object
		cancel : True jika sedang melakukan cancel/reverse
	"""
	gl_entries = []

	# Filter hanya item non-stock
	non_stock_items = [item for item in doc.items if frappe.get_doc("Item", item.item_code).is_stock_item == 0]

	if not non_stock_items:
		return

	# ── Credit Account ────────────────────────────────────────────────────────
	# Ambil dari doctype Procurement Settings → tabel ap_in_transit_po_
	# cari baris yang company-nya sama dengan Purchase Receipt
	credit_account = _get_ap_in_transit_account(1, doc.company)

	# ── Buat GL Entry per item ────────────────────────────────────────────────
	for item in non_stock_items:
		# Debit Account: Fixed Asset Account dari Asset Category → Company account
		if item.asset_category:
			debit_account = _get_fixed_asset_account(item.asset_category, doc.company)
		else:
			item_doc = frappe.get_doc("Item", item.item_code)
			for row in item_doc.item_defaults:
				if row.company == doc.company:
					debit_account = row.expense_account

		if not debit_account:
			frappe.throw(
				_(
					"Fixed Asset Account untuk Asset Category <b>{0}</b> "
					"dan Company <b>{1}</b> tidak ditemukan. "
					"Harap periksa pengaturan Asset Category Accounts."
				).format(item.asset_category, doc.company)
			)

		amount = flt(item.amount)  # amount sudah dalam base currency

		# GL Entry – Debit (Fixed Asset Account)
		gl_entries.append(
			_make_gl_entry(
				doc=doc,
				account=debit_account,
				debit=amount,
				credit=0.0,
				against=doc.supplier,
				remarks=f"Non-stock item: {item.item_code} - {item.item_name}",
				cancel=cancel,
				party="",
				party_type=""
			)
		)

		# GL Entry – Credit (AP in Transit Account)
		gl_entries.append(
			_make_gl_entry(
				doc=doc,
				account=credit_account,
				debit=0.0,
				credit=amount,
				against=debit_account,
				remarks=f"Non-stock item: {item.item_code} - {item.item_name}",
				cancel=cancel,
				party="",
				party_type=""
			)
		)

	debit_account = _get_fixed_asset_account(doc.items[0].asset_category, doc.company)

	gl_entries.append(
		_make_gl_entry(
			doc=doc,
			account=debit_account,
			debit=doc.total_taxes_and_charges,
			credit=0.0,
			against=doc.supplier,
			remarks=f"Non-stock item: {item.item_code} - {item.item_name}",
			cancel=cancel,
			party="",
			party_type=""
		)
	)

	# GL Entry – Credit (AP in Transit Account)
	gl_entries.append(
		_make_gl_entry(
			doc=doc,
			account=credit_account,
			debit=0.0,
			credit=doc.total_taxes_and_charges,
			against=debit_account,
			remarks=f"Non-stock item: {item.item_code} - {item.item_name}",
			cancel=cancel,
			party="",
			party_type=""
		)
	)

	# ── Simpan GL Entries ─────────────────────────────────────────────────────
	if gl_entries:
		_save_gl_entries(gl_entries, cancel)

	return gl_entries


# ─── Helper: Ambil AP in Transit Account dari Supplier ───────────────────────

def _get_ap_in_transit_account(service: int, company: str) -> str | None:
	expense_account = ""
	if service == 1:
		expense_account = method_ambil_account.ambil_ap_in_transit_procurement("jasa", company)
	else:
		expense_account = method_ambil_account.ambil_ap_in_transit_procurement("barang", company)

	return expense_account


# ─── Helper: Ambil Fixed Asset Account dari Asset Category ───────────────────

def _get_fixed_asset_account(asset_category: str, company: str) -> str | None:
	"""
	Baca tabel accounts di doctype Asset Category,
	kembalikan field `fixed_asset_account` untuk baris yang company-nya cocok.
	"""
	if not asset_category:
		return None

	asset_cat = frappe.get_doc("Asset Category", asset_category)

	for row in asset_cat.get("accounts", []):
		if row.company_name == company:
			return row.fixed_asset_account

	return None


# ─── Helper: Buat dict GL Entry ──────────────────────────────────────────────

def _make_gl_entry(
	doc,
	account: str,
	debit: float,
	credit: float,
	against: str,
	remarks: str,
	cancel: bool,
	party: str,
	party_type: str
) -> dict:
	"""Kembalikan dict yang siap dimasukkan ke tabungan GL Entry."""
	# Jika cancel, balik debit/credit
	if cancel:
		debit, credit = credit, debit

	return frappe._dict({
		"doctype": "GL Entry",
		"posting_date": doc.posting_date,
		"transaction_date": doc.posting_date,
		"account": account,
		"against": against,
		"debit": debit,
		"credit": credit,
		"debit_in_account_currency": debit,
		"credit_in_account_currency": credit,
		"against_voucher_type": doc.doctype,
		"against_voucher": doc.name,
		"voucher_type": doc.doctype,
		"voucher_no": doc.name,
		"cost_center": doc.cost_center or frappe.db.get_value(
			"Company", doc.company, "cost_center"
		),
		"company": doc.company,
		"remarks": remarks,
		"is_cancelled": 1 if cancel else 0,
		"party_type": party_type,
		"party": party
	})


# ─── Helper: Simpan GL Entries ke database ───────────────────────────────────

def _save_gl_entries(gl_entries: list[dict], cancel: bool):
	"""Insert atau cancel GL Entry ke Frappe."""
	from erpnext.accounts.general_ledger import make_gl_entries

	make_gl_entries(gl_entries, cancel=cancel, adv_adj=False)


@frappe.whitelist()
def make_purchase_invoice(source_name, target_doc=None, args=None):
	from erpnext.accounts.party import get_payment_terms_template
	from erpnext.stock.doctype.purchase_receipt.purchase_receipt import get_returned_qty_map,get_invoiced_qty_map,merge_taxes

	doc = frappe.get_doc("Purchase Receipt", source_name)
	returned_qty_map = get_returned_qty_map(source_name)
	invoiced_qty_map = get_invoiced_qty_map(source_name)

	def set_missing_values(source, target):
		if len(target.get("items")) == 0:
			frappe.throw(_("All items have already been Invoiced/Returned"))

		doc = frappe.get_doc(target)
		doc.payment_terms_template = get_payment_terms_template(source.supplier, "Supplier", source.company)
		doc.run_method("onload")
		doc.run_method("set_missing_values")

		if args and args.get("merge_taxes"):
			merge_taxes(source.get("taxes") or [], doc)

		doc.run_method("calculate_taxes_and_totals")
		doc.set_payment_schedule()

	def update_item(source_doc, target_doc, source_parent):
		target_doc.qty, returned_qty = get_pending_qty(source_doc)
		if frappe.db.get_single_value("Buying Settings", "bill_for_rejected_quantity_in_purchase_invoice"):
			target_doc.rejected_qty = 0
		target_doc.stock_qty = flt(target_doc.qty) * flt(
			target_doc.conversion_factor, target_doc.precision("conversion_factor")
		)
		returned_qty_map[source_doc.name] = returned_qty

	def get_pending_qty(item_row):
		qty = item_row.qty
		if frappe.db.get_single_value("Buying Settings", "bill_for_rejected_quantity_in_purchase_invoice"):
			qty = item_row.received_qty

		pending_qty = qty - invoiced_qty_map.get(item_row.name, 0)

		if frappe.db.get_single_value("Buying Settings", "bill_for_rejected_quantity_in_purchase_invoice"):
			return pending_qty, 0

		returned_qty = flt(returned_qty_map.get(item_row.name, 0))
		if item_row.rejected_qty and returned_qty:
			returned_qty -= item_row.rejected_qty

		if returned_qty:
			if returned_qty >= pending_qty:
				pending_qty = 0
				returned_qty -= pending_qty
			else:
				pending_qty -= returned_qty
				returned_qty = 0

		return pending_qty, returned_qty

	doclist = get_mapped_doc(
		"Purchase Receipt",
		source_name,
		{
			"Purchase Receipt": {
				"doctype": "Purchase Invoice",
				"field_map": {
					"supplier_warehouse": "supplier_warehouse",
					"is_return": "is_return",
					"bill_date": "bill_date",
				},
				"validation": {
					"docstatus": ["=", 1],
				},
			},
			"Purchase Receipt Item": {
				"doctype": "Purchase Invoice Item",
				"field_map": {
					"name": "pr_detail",
					"parent": "purchase_receipt",
					"qty": "received_qty",
					"purchase_order_item": "po_detail",
					"purchase_order": "purchase_order",
					"is_fixed_asset": "is_fixed_asset",
					"asset_location": "asset_location",
					"asset_category": "asset_category",
					"wip_composite_asset": "wip_composite_asset",
				},
				"postprocess": update_item,
				"filter": lambda d: get_pending_qty(d)[0] <= 0
				if not doc.get("is_return")
				else get_pending_qty(d)[0] > 0,
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

	if doc.purchase_order:
		po_doc = frappe.get_doc("Purchase Order", doc.purchase_order)
		if po_doc.sub_purchase_type == "Purchase Request":
			doclist.invoice_type = "Purchase Order"
		elif po_doc.sub_purchase_type == "Service Request":
			doclist.invoice_type = "Service Order"


	return doclist
