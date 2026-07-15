# Copyright (c) 2026, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import json

import frappe
import erpnext
from frappe import _, throw
from frappe.query_builder.functions import Sum
from frappe.utils import cint, flt, getdate, get_link_to_form
from erpnext.assets.doctype.asset_category.asset_category import get_asset_category_account
from erpnext.accounts.doctype.purchase_invoice.purchase_invoice import PurchaseInvoice,make_regional_gl_entries, get_purchase_document_details
from erpnext.assets.doctype.asset.asset import is_cwip_accounting_enabled
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import (
	update_billed_amount_based_on_po,
)
from erpnext.accounts.doctype.sales_invoice.sales_invoice import (
	get_total_in_party_account_currency,
	is_overdue
)

from erpnext.accounts.general_ledger import (
	get_round_off_account_and_cost_center,
	make_gl_entries,
	make_reverse_gl_entries,
	merge_similar_entries,
)

from sth.legal.doctype.bapp.bapp import (
	update_billed_amount_based_on_proposal,
)

from erpnext.stock.doctype.purchase_receipt.purchase_receipt import (
	get_item_account_wise_additional_cost,
	update_billed_amount_based_on_po,
)

from erpnext.stock import get_warehouse_account_map
from erpnext.accounts.utils import get_account_currency, get_fiscal_year, update_voucher_outstanding

form_grid_templates = {"items": "/home/frappe/frappe-bench/apps/sth/sth/templates/form_grid/custom_item_grid.html","non_voucher_match": "templates/form_grid/non_voucher_grid.html"}

from sth.custom import method_ambil_account

class SthPurchaseInvoice(PurchaseInvoice):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.status_updater.append(
			{
				"source_dt": "Purchase Invoice Item",
				"target_dt": "Proposal Item",
				"join_field": "proposal_detail",
				"target_field": "billed_amt",
				"target_parent_dt": "Proposal",
				"target_parent_field": "per_billed",
				"target_ref_field": "amount",
				"source_field": "amount",
				"percent_join_field": "proposal",
				"overflow_type": "billing",
			}
		)

	def before_submit(self):
		pass

	def validate(self):
		update_cwip_expense_accounts(self)
		bukan_dp = 0
		if self.termin == "DP":
			bukan_dp = 1
		service = 0

		ada_po = 0
		ada_pro = 0

		for item in self.items:
			if item.purchase_order:
				ada_po = 1
				po_doc = frappe.get_doc("Purchase Order", item.purchase_order)
				if po_doc.sub_purchase_type == "Service Request":
					service = 1

				akun_expense = ""

				if bukan_dp == 0:
					if service == 1:
						akun_expense = method_ambil_account.ambil_ap_in_transit_procurement("jasa", self.company)
						self.credit_to = method_ambil_account.ambil_hutang_invoice_procurement("jasa", self.company)
					else:
						akun_expense = method_ambil_account.ambil_ap_in_transit_procurement("barang", self.company)
						self.credit_to = method_ambil_account.ambil_hutang_invoice_procurement("barang", self.company)

					# print(akun_expense)
					item.expense_account = akun_expense

				else:
					if service == 1:
						akun_expense = method_ambil_account.ambil_uang_muka_procurement("jasa", self.company)
						self.credit_to = method_ambil_account.ambil_hutang_invoice_procurement("jasa", self.company)
					else:
						akun_expense = method_ambil_account.ambil_uang_muka_procurement("barang", self.company)
						self.credit_to = method_ambil_account.ambil_hutang_invoice_procurement("barang", self.company)

					item.expense_account = akun_expense
					self.credit_amount = method_ambil_account.ambil_hutang_invoice_procurement(po_doc.name,self.company)

			if item.proposal:
				ada_pro = 1
				po_doc = frappe.get_doc("Proposal", item.proposal)

				if bukan_dp == 0:
					item.expense_account = method_ambil_account.ambil_proposal_hutang_usaha(po_doc.name,self.company)
				else:
					item.expense_account = method_ambil_account.ambil_proposal_uang_muka(po_doc.name,self.company)

				self.credit_to = method_ambil_account.ambil_proposal_hutang_invoice(po_doc.name,self.company)

			if ada_po == 0 and ada_pro == 0:
				for item in self.items:
					doc_item = frappe.get_doc("Item", item.item_code)
					for row_item in doc_item.item_defaults:
						if self.company == row_item.company:
							item.expense_account = row_item.expense_account

		if self.voucher_type == "Non Voucher Match":
			for row in self.non_voucher_match:
				if row.kendaraan:
					self.cost_center = get_or_create_cost_center(row.kendaraan, self.company)

		super().validate()
		self.validate_term()
		self.set_retensi_amount()
		self.set_charges_total()

	def set_expense_account(self, for_validate=False):
		auto_accounting_for_stock = erpnext.is_perpetual_inventory_enabled(self.company)

		if auto_accounting_for_stock:
			stock_not_billed_account = self.get_company_default("stock_received_but_not_billed")
			stock_items = self.get_stock_items()

		self.asset_received_but_not_billed = None

		if self.update_stock:
			self.validate_item_code()
			self.validate_warehouse(for_validate)
			if auto_accounting_for_stock:
				warehouse_account = get_warehouse_account_map(self.company)

		for item in self.get("items"):
			# in case of auto inventory accounting,
			# expense account is always "Stock Received But Not Billed" for a stock item
			# except opening entry, drop-ship entry and fixed asset items
			if (
				auto_accounting_for_stock
				and item.item_code in stock_items
				and self.is_opening == "No"
				and not item.is_fixed_asset
				and (
					not item.po_detail
					or not frappe.db.get_value("Purchase Order Item", item.po_detail, "delivered_by_supplier")
				)
			):
				if self.update_stock and item.warehouse and (not item.from_warehouse):
					if (
						for_validate
						and item.expense_account
						and item.expense_account != warehouse_account[item.warehouse]["account"]
					):
						msg = _(
							"Row {0}: Expense Head changed to {1} because account {2} is not linked to warehouse {3} or it is not the default inventory account"
						).format(
							item.idx,
							frappe.bold(warehouse_account[item.warehouse]["account"]),
							frappe.bold(item.expense_account),
							frappe.bold(item.warehouse),
						)
						# frappe.msgprint(msg, title=_("Expense Head Changed"))
					# item.expense_account = warehouse_account[item.warehouse]["account"]
				else:
					# check if 'Stock Received But Not Billed' account is credited in Purchase receipt or not
					if item.purchase_receipt:
						negative_expense_booked_in_pr = frappe.db.sql(
							"""select name from `tabGL Entry`
							where voucher_type='Purchase Receipt' and voucher_no=%s and account = %s""",
							(item.purchase_receipt, stock_not_billed_account),
						)

						if negative_expense_booked_in_pr:
							if (
								for_validate
								and item.expense_account
								and item.expense_account != stock_not_billed_account
							):
								msg = _(
									"Row {0}: Expense Head changed to {1} because expense is booked against this account in Purchase Receipt {2}"
								).format(
									item.idx,
									frappe.bold(stock_not_billed_account),
									frappe.bold(item.purchase_receipt),
								)
								# frappe.msgprint(msg, title=_("Expense Head Changed"))

							# item.expense_account = stock_not_billed_account
					else:
						# If no purchase receipt present then book expense in 'Stock Received But Not Billed'
						# This is done in cases when Purchase Invoice is created before Purchase Receipt
						if (
							for_validate
							and item.expense_account
							and item.expense_account != stock_not_billed_account
						):
							msg = _(
								"Row {0}: Expense Head changed to {1} as no Purchase Receipt is created against Item {2}."
							).format(
								item.idx, frappe.bold(stock_not_billed_account), frappe.bold(item.item_code)
							)
							msg += "<br>"
							msg += _(
								"This is done to handle accounting for cases when Purchase Receipt is created after Purchase Invoice"
							)
							# frappe.msgprint(msg, title=_("Expense Head Changed"))

						# item.expense_account = stock_not_billed_account
			elif item.is_fixed_asset:
				account = None
				if not item.pr_detail and item.po_detail:
					receipt_item = frappe.get_cached_value(
						"Purchase Receipt Item",
						{
							"purchase_order": item.purchase_order,
							"purchase_order_item": item.po_detail,
							"docstatus": 1,
						},
						["name", "parent"],
						as_dict=1,
					)
					if receipt_item:
						item.pr_detail = receipt_item.name
						item.purchase_receipt = receipt_item.parent

				if item.pr_detail:
					if not self.asset_received_but_not_billed:
						self.asset_received_but_not_billed = self.get_company_default(
							"asset_received_but_not_billed"
						)

					# check if 'Asset Received But Not Billed' account is credited in Purchase receipt or not
					arbnb_booked_in_pr = frappe.db.get_value(
						"GL Entry",
						{
							"voucher_type": "Purchase Receipt",
							"voucher_no": item.purchase_receipt,
							"account": self.asset_received_but_not_billed,
						},
						"name",
					)
					if arbnb_booked_in_pr:
						account = self.asset_received_but_not_billed

				if not account:
					account_type = (
						"capital_work_in_progress_account"
						if is_cwip_accounting_enabled(item.asset_category)
						else "fixed_asset_account"
					)
					account = get_asset_category_account(
						account_type, item=item.item_code, company=self.company
					)
					if not account:
						form_link = get_link_to_form("Asset Category", item.asset_category)
						throw(
							_("Please set Fixed Asset Account in {} against {}.").format(
								form_link, self.company
							),
							title=_("Missing Account"),
						)
				# item.expense_account = account
			elif not item.expense_account and for_validate:
				print(str(frappe.as_json(item)))
				throw(_("Expense account is mandatory for item {0}").format(item.item_code or item.item_name))
				
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
					"allow_duplicate_prev_row_id": True,
				},
				"Proposal": {
					"ref_dn_field": "proposal",
					# "compare_fields": [["supplier", "="], ["company", "="], ["currency", "="]],
					"compare_fields": [["company", "="], ["currency", "="]],
				},
				"Proposal Item": {
					"ref_dn_field": "proposal_detail",
					# "compare_fields": [["project", "="], ["item_code", "="], ["kegiatan", "="], ["kegiatan_name", "="], ["uom", "="]],
					"compare_fields": [["project", "="], ["kegiatan", "="], ["uom", "="]],
					"is_child_table": True,
					"allow_duplicate_prev_row_id": True,
				},
				"BAPP": {
					"ref_dn_field": "bapp",
					# "compare_fields": [["supplier", "="], ["company", "="], ["currency", "="]],
					"compare_fields": [["company", "="], ["currency", "="]],
				},
				"BAPP Item": {
					"ref_dn_field": "bapp_detail",
					# "compare_fields": [["project", "="], ["item_code", "="], ["kegiatan", "="], ["kegiatan_name", "="], ["uom", "="]],
					"compare_fields": [["project", "="], ["kegiatan", "="], ["uom", "="]],
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
			elif d.bapp_detail and not d.proposal_detail:
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

		if self.invoice_type == "SPK" and self.document_no not in updated_bapp:
			bapp_doc = frappe.get_doc("BAPP", self.document_no)
			bapp_doc.db_set("per_billed", 100 if self.docstatus == 1 else 0)

			if update_modified:
				bapp_doc.set_status(update=True)
				bapp_doc.notify_update()

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

	# def set_retensi_amount(self):
	# 	self.retensi_amount = flt(self.net_total * self.retensi/100, self.precision("retensi_amount"))

	def set_charges_total(self):
		self.total_charges = sum(
			flt(row.total) for row in self.get("charges_purchase_invoice")
		)

	def set_retensi_amount(self):
		self.retensi_amount = flt(self.rounded_total or self.grand_total) \
			if self.term_detail and self.payment_term in ("Retensi") \
			else flt(
				self.net_total * flt(self.retensi)/100,
				self.precision("retensi_amount")
			)

	def validate_term(self):
		if not self.term_detail:
			self.payment_term = ""
			return

		term, self.payment_term = frappe.db.get_value("Proposal Schedule", self.term_detail, ["term_used", "payment_term"], for_update=1)
		if term:
			frappe.throw(f"Term {self.payment_term} already used")

	def on_submit(self):
		super().on_submit()
		self.update_term_used()

	def on_cancel(self):
		super().on_cancel()
		self.update_term_used(cancel=1)

	def update_term_used(self, cancel=0):
		if not self.term_detail:
			return

		frappe.db.set_value("Proposal Schedule", self.term_detail, "term_used", not cancel)

	def set_status(self, update=False, status=None, update_modified=True):
		if self.is_new():
			if self.get("amended_from"):
				self.status = "Draft"
			return

		outstanding_amount = flt(self.outstanding_amount, self.precision("outstanding_amount"))
		total = get_total_in_party_account_currency(self)

		# ceck jika ada retensi dan
		if self.retensi and not self.retensi_paid and outstanding_amount < self.retensi_amount:
			frappe.throw(f"Outstanding can't less than {self.retensi_amount} because there is still a Restan to confirm")

		if not status:
			if self.docstatus == 2:
				status = "Cancelled"
			elif self.docstatus == 1:
				if self.is_internal_transfer():
					self.status = "Internal Transfer"
				elif is_overdue(self, total):
					self.status = "Overdue"
				elif 0 < outstanding_amount < total:
					self.status = "Partly Paid"
				elif outstanding_amount > 0 and getdate(self.due_date) >= getdate():
					self.status = "Unpaid"
				# Check if outstanding amount is 0 due to debit note issued against invoice
				elif self.is_return == 0 and frappe.db.get_value(
					"Purchase Invoice", {"is_return": 1, "return_against": self.name, "docstatus": 1}
				):
					self.status = "Debit Note Issued"
				elif self.is_return == 1:
					self.status = "Return"
				elif outstanding_amount <= 0:
					self.status = "Paid"
				else:
					self.status = "Submitted"
			else:
				self.status = "Draft"

		if update:
			self.db_set("status", self.status, update_modified=update_modified)

	def get_gl_entries(self, warehouse_account=None):

		self.auto_accounting_for_stock = erpnext.is_perpetual_inventory_enabled(self.company)
		if self.auto_accounting_for_stock:
			self.stock_received_but_not_billed = self.get_company_default("stock_received_but_not_billed")
		else:
			self.stock_received_but_not_billed = None

		self.negative_expense_to_be_booked = 0.0
		gl_entries = []

		if self.invoice_type == "SPK":
			self.make_item_gl_entries_spk(gl_entries)
			self.make_tax_gl_entries(gl_entries)
			# self.make_charges_gl_entries(gl_entries)

			gl_entries = merge_similar_entries(gl_entries)

			self.set_transaction_currency_and_rate_in_gl_map(gl_entries)

		elif self.invoice_type == "Leasing" or self.invoice_type == "Sewa":
			self.make_item_gl_entries_leasing(gl_entries)
			self.make_tax_gl_entries(gl_entries)
			# self.make_charges_gl_entries(gl_entries)

			gl_entries = merge_similar_entries(gl_entries)

			self.set_transaction_currency_and_rate_in_gl_map(gl_entries)

		else:
			self.make_supplier_gl_entry(gl_entries)
			
			if self.invoice_type == "Purchase Order":
				self.make_item_gl_entries_custom(gl_entries)
			else:
				self.make_item_gl_entries_custom(gl_entries)

			
			self.make_precision_loss_gl_entry(gl_entries)

			# Tax di-skip untuk SPK
			if self.invoice_type != "SPK":
				self.make_tax_gl_entries(gl_entries)
				self.make_internal_transfer_gl_entries(gl_entries)
				self.make_gl_entries_for_tax_withholding(gl_entries)

			
			gl_entries = make_regional_gl_entries(gl_entries, self)
			gl_entries = merge_similar_entries(gl_entries)
			self.make_payment_gl_entries(gl_entries)
			self.make_write_off_gl_entry(gl_entries)
			self.make_gle_for_rounding_adjustment(gl_entries)
			self.set_transaction_currency_and_rate_in_gl_map(gl_entries)

		return gl_entries

	def make_supplier_gl_entry(self, gl_entries):
		# Checked both rounding_adjustment and rounded_total
		# because rounded_total had value even before introduction of posting GLE based on rounded total
		grand_total = (
			self.rounded_total if (self.rounding_adjustment and self.rounded_total) else self.grand_total
		)
		base_grand_total = flt(
			self.base_rounded_total
			if (self.base_rounding_adjustment and self.base_rounded_total)
			else self.base_grand_total,
			self.precision("base_grand_total"),
		)


		base_grand_total = flt(base_grand_total, self.precision("base_grand_total"))
		grand_total = flt(grand_total, self.precision("grand_total"))

		if grand_total and not self.is_internal_transfer():
			self.add_supplier_gl_entry(gl_entries, base_grand_total, grand_total)

	def add_supplier_gl_entry(
		self, gl_entries, base_grand_total, grand_total, against_account=None, remarks=None, skip_merge=False
	):
		against_voucher = self.name
		if self.is_return and self.return_against and not self.update_outstanding_for_self:
			against_voucher = self.return_against

		# total_qty = 0
		# total_pph_qty = 0
		# for item in self.items:
		# 	if item.pph == 1:
		# 		total_pph_qty += item.qty

		# 	total_qty += item.qty

		# for item in self.items:
		# 	if not total_qty:
		# 		continue

		# 	qty_fraction = 1
		# 	if total_pph_qty:
		# 		qty_fraction = item.qty / total_pph_qty

		# 	item_base_credit = item.qty * item.base_rate
		# 	item_credit = item.qty * item.rate

		# 	if item.pph == 1:
		# 		item_base_credit -= (self.total_pph_lainnya) * qty_fraction
		# 		item_credit -= (self.total_pph_lainnya) * qty_fraction

			# gl = {
			# 	"account": self.credit_to,
			# 	"party_type": "Supplier",
			# 	"party": self.supplier,
			# 	"due_date": self.due_date,
			# 	"against": against_account or self.against_expense_account,
			# 	"credit": item_base_credit,
			# 	"credit_in_account_currency": item_base_credit
			# 	if self.party_account_currency == self.company_currency
			# 	else item_credit,
			# 	"credit_in_transaction_currency": item_credit,
			# 	"against_voucher": against_voucher,
			# 	"against_voucher_type": self.doctype,
			# 	"project": item.project or self.project,
			# 	"cost_center": self.cost_center or frappe.db.get_value(
			# 			"Company", self.company, "cost_center"
			# 		),
			# 	"_skip_merge": skip_merge,
			# 	"voucher_detail_no": item.name
			# }
			# if remarks:
			# 	gl["remarks"] = remarks

			# gl_entries.append(self.get_gl_dict(gl, self.party_account_currency, item=item))

		gl = {
			"account": self.credit_to,
			"party_type": "Supplier",
			"party": self.supplier,
			"due_date": self.due_date,
			"against": against_account or self.against_expense_account,
			"credit": self.grand_total,
			"credit_in_account_currency": self.grand_total
			if self.party_account_currency == self.company_currency
			else self.grand_total,
			"credit_in_transaction_currency": self.grand_total,
			"against_voucher": against_voucher,
			"against_voucher_type": self.doctype,
			"project": self.project,
			"cost_center": self.cost_center or frappe.db.get_value(
					"Company", self.company, "cost_center"
				),
			"_skip_merge": skip_merge
		}
		if remarks:
			gl["remarks"] = remarks

		gl_entries.append(self.get_gl_dict(gl, self.party_account_currency))

	def make_charges_gl_entries(self, gl_entries):
		for tax in self.get("taxes"):			
			if tax.description != "__from_charges__":
				continue

			amount = tax.tax_amount
			base_amount = tax.tax_amount

			if not flt(base_amount):
				continue

			account_currency = get_account_currency(tax.account_head)
			dr_or_cr = "debit" if tax.add_deduct_tax == "Add" else "credit"

			gl_entries.append(
				self.get_gl_dict(
					{
						"account": tax.account_head,
						"against": self.supplier,
						dr_or_cr: base_amount,
						dr_or_cr + "_in_account_currency": base_amount
						if account_currency == self.company_currency
						else amount,
						dr_or_cr + "_in_transaction_currency": amount,
						"cost_center": tax.cost_center or self.cost_center or frappe.db.get_value(
							"Company", self.company, "cost_center"
						),
					},
					account_currency,
					item=tax,
				)
			)

	def make_tax_gl_entries(self, gl_entries):
		# tax table gl entries
		valuation_tax = {}

		for tax in self.get("taxes"):
			amount, base_amount = self.get_tax_amounts(tax, None)
			if tax.category in ("Total", "Valuation and Total") and flt(base_amount) and (
				"__from_pph_lainnya__" in (tax.description or "")
				or "__from_ppn__" in (tax.description or "")
				or "__from_charges__" in (tax.description or "")
				or "__from_pb__" in (tax.description or "")
			):
				account_currency = get_account_currency(tax.account_head)

				dr_or_cr = "debit" if tax.add_deduct_tax == "Add" else "credit"
				# if "__from_charges__" in tax.description:
				# 	base_amount = base_amount * -1

				gl_entries.append(
					self.get_gl_dict(
						{
							"account": tax.account_head,
							"against": self.supplier,
							dr_or_cr: base_amount,
							dr_or_cr + "_in_account_currency": base_amount
							if account_currency == self.company_currency
							else amount,
							dr_or_cr + "_in_transaction_currency": amount,
							"cost_center": tax.cost_center,
						},
						account_currency,
						item=tax,
					)
				)
			# accumulate valuation tax
			if (
				self.is_opening == "No"
				and tax.category in ("Valuation", "Valuation and Total")
				and flt(base_amount)
				and not self.is_internal_transfer()
			):
				if self.auto_accounting_for_stock and not tax.cost_center:
					frappe.throw(
						_("Cost Center is required in row {0} in Taxes table for type {1}").format(
							tax.idx, _(tax.category)
						)
					)
				valuation_tax.setdefault(tax.name, 0)
				valuation_tax[tax.name] += (tax.add_deduct_tax == "Add" and 1 or -1) * flt(base_amount)

		if self.is_opening == "No" and self.negative_expense_to_be_booked and valuation_tax:
			# credit valuation tax amount in "Expenses Included In Valuation"
			# this will balance out valuation amount included in cost of goods sold

			total_valuation_amount = sum(valuation_tax.values())
			amount_including_divisional_loss = self.negative_expense_to_be_booked
			i = 1
			for tax in self.get("taxes"):
				if valuation_tax.get(tax.name) and "PPH 21" in tax.account_head:
					if i == len(valuation_tax):
						applicable_amount = amount_including_divisional_loss
					else:
						applicable_amount = self.negative_expense_to_be_booked * (
							valuation_tax[tax.name] / total_valuation_amount
						)
						amount_including_divisional_loss -= applicable_amount

					gl_entries.append(
						self.get_gl_dict(
							{
								"account": tax.account_head,
								"cost_center": tax.cost_center,
								"against": self.supplier,
								"credit": applicable_amount,
								"credit_in_transaction_currency": flt(
									applicable_amount / self.conversion_rate,
									frappe.get_precision("Purchase Invoice Item", "item_tax_amount"),
								),
								"remarks": self.remarks or _("Accounting Entry for Stock"),
								"cost_center": self.cost_center or frappe.db.get_value(
									"Company", self.company, "cost_center"
								),
							},
							item=tax,
						)
					)

					i += 1

		if self.auto_accounting_for_stock and self.update_stock and valuation_tax:
			for tax in self.get("taxes"):
				if valuation_tax.get(tax.name) and ("PPH 21" in tax.account_head or "__from_charges__" in tax.description):
					gl_entries.append(
						self.get_gl_dict(
							{
								"account": tax.account_head,
								"cost_center": tax.cost_center,
								"against": self.supplier,
								"credit": valuation_tax[tax.name],
								"credit_in_transaction_currency": flt(
									valuation_tax[tax.name] / self.conversion_rate,
									frappe.get_precision("Purchase Invoice Item", "item_tax_amount"),
								),
								"remarks": self.remarks or _("Accounting Entry for Stock"),
								"cost_center": self.cost_center or frappe.db.get_value(
									"Company", self.company, "cost_center"
								),
							},
							item=tax,
						)
					)


	def make_item_gl_entries_spk(self, gl_entries):
		
		remarks = self.get("remarks") or _(
			"Accounting Entry for {0} {1}"
		).format(self.doctype, self.name)

		total_debit = 0.0

		# ── DEBIT : expense_account per item ────────────────────────────────── #
		for item in self.get("items"):
			base_amount = flt(item.base_amount)
			if not base_amount:
				continue

			if not item.expense_account:
				frappe.throw(
					_("Baris {0} (Item: <b>{1}</b>): <b>Expense Account</b> belum diisi.").format(
						item.idx, item.item_code or item.item_name
					)
				)

			# Untuk multi-currency: amount_in_account_currency = amount (mata uang transaksi)
			amount_in_txn_currency = flt(item.amount)
			gl_entries.append(
				self.get_gl_dict(
					{
						"account"                    : item.expense_account,
						"debit"                      : base_amount,
						"debit_in_account_currency"  : (
							amount_in_txn_currency
							if self.party_account_currency != self.company_currency
							else base_amount
						),
						"against"                    : self.credit_to,

						"cost_center"				 : self.cost_center or frappe.db.get_value(
														"Company", self.company, "cost_center"
													   ),
						"project"                    : item.project or self.project,
						"remarks"                    : remarks,
						"voucher_detail_no"          : item.name,
					},
					item.get("account_currency") or self.company_currency,
				)
			)

			total_debit += base_amount

		if not total_debit:
			return

		total_charges_pp = 0
		for tax in self.taxes:
			if ("__from_pph_lainnya__" in (tax.description or "")
				or "__from_ppn__" in (tax.description or "")
				or "__from_charges__" in (tax.description or "")
				or "__from_pb__" in (tax.description or "")):

				if "__from_charges__" in (tax.description or ""):
					total_charges_pp += tax.tax_amount * -1
				else:
					total_charges_pp += tax.tax_amount

		# Kurangi credit_to dengan total charges (charges punya GL entry sendiri via make_charges_gl_entries)
		credit_amount = flt(total_debit + total_charges_pp, self.precision("base_grand_total"))

		# ── CREDIT : credit_to (hutang ke supplier) ──────────────────────────── #
		# Kumpulkan semua expense_account unik sebagai "against" label
		against_accounts = ", ".join(
			sorted({item.expense_account for item in self.get("items") if item.expense_account})
		)

		# Nilai credit dalam mata uang party (jika multi-currency)
		if self.party_account_currency == self.company_currency:
			credit_in_party_currency = credit_amount
		else:
			# Hitung ulang dari item.amount (mata uang transaksi) dikurangi charges
			credit_in_party_currency = flt(
				sum(flt(item.amount) for item in self.get("items") if flt(item.amount))
			) - flt(self.total_charges)

		gl_entries.append(
			self.get_gl_dict(
				{
					"account"                   : self.credit_to,
					"party_type"                : "Supplier",
					"party"                     : self.supplier,
					"credit"                    : credit_amount,              # base (IDR)
					"credit_in_account_currency": credit_in_party_currency,  # mata uang party
					"against"                   : against_accounts,
					"remarks"                   : remarks,

					"cost_center": self.cost_center or frappe.db.get_value(
						"Company", self.company, "cost_center"
					),
				},
				self.party_account_currency,
			)
		)

	def make_item_gl_entries_leasing(self, gl_entries):
		"""
		GL Entries untuk Purchase Invoice dengan invoice_type == 'Leasing'.
		Charges dikurangi dari base_amount; GL entry charges dibuat via make_charges_gl_entries.
		"""
		remarks = (
			"Keterangan {2}. Accounting Entry for {0} {1}. "
		).format(self.doctype, self.name, self.keterangan)

		grand_total = flt(self.grand_total)
		base_amount = flt(self.grand_total)

		service = 1

		supplier_hutang_leasing_account = ""
		if service == 1:
			supplier_hutang_leasing_account = method_ambil_account.ambil_hutang_invoice_procurement("jasa", self.company)
		else:
			supplier_hutang_leasing_account = method_ambil_account.ambil_hutang_invoice_procurement("barang", self.company)

		supplier_ap_in_transit_account = ""
		if service == 1:
			supplier_ap_in_transit_account = method_ambil_account.ambil_ap_in_transit_procurement("jasa", self.company)
		else:
			supplier_ap_in_transit_account = method_ambil_account.ambil_ap_in_transit_procurement("barang", self.company)

		acc_doc = frappe.get_doc("Account", supplier_ap_in_transit_account)
		if acc_doc.account_type == "Payable":
			gl_entries.append(
				self.get_gl_dict(
					{
						"account"                    : supplier_ap_in_transit_account,
						"debit"                      : base_amount,
						"debit_in_account_currency"  : base_amount,
						"against"                    : supplier_hutang_leasing_account,
						"cost_center"                : self.cost_center,
						"project"                    : self.project,
						"remarks"                    : remarks,
						"party_type"                 : "Supplier",
						"party"                      : self.supplier,
					},
					self.company_currency,
				)
			)
		else:
			gl_entries.append(
				self.get_gl_dict(
					{
						"account"                    : supplier_ap_in_transit_account,
						"debit"                      : base_amount,
						"debit_in_account_currency"  : base_amount,
						"against"                    : supplier_hutang_leasing_account,
						"cost_center"                : self.cost_center,
						"project"                    : self.project,
						"remarks"                    : remarks,
					},
					self.company_currency,
				)
			)

		acc_doc = frappe.get_doc("Account", supplier_hutang_leasing_account)
		if acc_doc.account_type == "Payable":
			gl_entries.append(
				self.get_gl_dict(
					{
						"account"                    : supplier_hutang_leasing_account,
						"credit"                     : grand_total,
						"credit_in_account_currency" : grand_total,
						"against"                    : supplier_ap_in_transit_account,
						"cost_center"                : self.cost_center,
						"project"                    : self.project,
						"remarks"                    : remarks,
						"party_type"                 : "Supplier",
						"party"                      : self.supplier,
					},
					self.company_currency,
				)
			)
		else:
			gl_entries.append(
				self.get_gl_dict(
					{
						"account"                    : supplier_hutang_leasing_account,
						"credit"                     : grand_total,
						"credit_in_account_currency" : grand_total,
						"against"                    : supplier_ap_in_transit_account,
						"cost_center"                : self.cost_center,
						"project"                    : self.project,
						"remarks"                    : remarks,
					},
					self.company_currency,
				)
			)

	def make_item_gl_entries_custom(self, gl_entries):
		# item gl entries
		stock_items = self.get_stock_items()
		if self.update_stock and self.auto_accounting_for_stock:
			warehouse_account = get_warehouse_account_map(self.company)

		landed_cost_entries = get_item_account_wise_additional_cost(self.name)

		voucher_wise_stock_value = {}
		if self.update_stock:
			stock_ledger_entries = frappe.get_all(
				"Stock Ledger Entry",
				fields=["voucher_detail_no", "stock_value_difference", "warehouse"],
				filters={"voucher_no": self.name, "voucher_type": self.doctype, "is_cancelled": 0},
			)
			for d in stock_ledger_entries:
				voucher_wise_stock_value.setdefault(
					(d.voucher_detail_no, d.warehouse), d.stock_value_difference
				)

		valuation_tax_accounts = [
			d.account_head
			for d in self.get("taxes")
			if d.category in ("Valuation", "Valuation and Total")
			and flt(d.base_tax_amount_after_discount_amount)
		]

		exchange_rate_map, net_rate_map = get_purchase_document_details(self)

		provisional_accounting_for_non_stock_items = cint(
			frappe.get_cached_value(
				"Company", self.company, "enable_provisional_accounting_for_non_stock_items"
			)
		)
		if provisional_accounting_for_non_stock_items:
			self.get_provisional_accounts()

		for item in self.get("items"):
			if flt(item.base_net_amount):
				if item.item_code:
					frappe.get_cached_value("Item", item.item_code, "asset_category")

				if (
					self.update_stock
					and self.auto_accounting_for_stock
					and (item.item_code in stock_items or item.is_fixed_asset)
				):
					account_currency = get_account_currency(item.expense_account)
					# warehouse account
					warehouse_debit_amount = self.make_stock_adjustment_entry(
						gl_entries, item, voucher_wise_stock_value, account_currency
					)

					if item.from_warehouse:
						gl_entries.append(
							self.get_gl_dict(
								{
									"account": warehouse_account[item.warehouse]["account"],
									"against": warehouse_account[item.from_warehouse]["account"],
									"cost_center": item.cost_center,
									"project": item.project or self.project,
									"remarks": self.get("remarks") or _("Accounting Entry for Stock"),
									"debit": warehouse_debit_amount,
									"debit_in_transaction_currency": item.net_amount,
								},
								warehouse_account[item.warehouse]["account_currency"],
								item=item,
							)
						)

						credit_amount = item.base_net_amount
						if self.is_internal_supplier and item.valuation_rate:
							credit_amount = flt(item.valuation_rate * item.stock_qty)

						# Intentionally passed negative debit amount to avoid incorrect GL Entry validation
						gl_entries.append(
							self.get_gl_dict(
								{
									"account": warehouse_account[item.from_warehouse]["account"],
									"against": warehouse_account[item.warehouse]["account"],
									"cost_center": item.cost_center,
									"project": item.project or self.project,
									"remarks": self.get("remarks") or _("Accounting Entry for Stock"),
									"debit": -1 * flt(credit_amount, item.precision("base_net_amount")),
									"debit_in_transaction_currency": item.net_amount,
								},
								warehouse_account[item.from_warehouse]["account_currency"],
								item=item,
							)
						)

						# Do not book expense for transfer within same company transfer
						if not self.is_internal_transfer():
							acc_doc = frappe.get_doc("Account", item.expense_account)
							if acc_doc.account_type == "Payable":
								gl_entries.append(
									self.get_gl_dict(
										{
											"account": item.expense_account,
											"against": self.supplier,
											"debit": flt(item.base_net_amount, item.precision("base_net_amount")),
											"debit_in_transaction_currency": item.net_amount,
											"remarks": self.get("remarks") or _("Accounting Entry for Stock"),
											"cost_center": item.cost_center,
											"project": item.project,
											"party_type": "Supplier",
											"party": self.supplier
										},
										account_currency,
										item=item,
									)
								)
							else:
								gl_entries.append(
									self.get_gl_dict(
										{
											"account": item.expense_account,
											"against": self.supplier,
											"debit": flt(item.base_net_amount, item.precision("base_net_amount")),
											"debit_in_transaction_currency": item.net_amount,
											"remarks": self.get("remarks") or _("Accounting Entry for Stock"),
											"cost_center": item.cost_center,
											"project": item.project,
										},
										account_currency,
										item=item,
									)
								)

					else:
						if not self.is_internal_transfer():
							acc_doc = frappe.get_doc("Account", item.expense_account)
							if acc_doc.account_type == "Payable":
								gl_entries.append(
									self.get_gl_dict(
										{
											"account": item.expense_account,
											"against": self.supplier,
											"debit": warehouse_debit_amount,
											"debit_in_transaction_currency": flt(
												warehouse_debit_amount / self.conversion_rate,
												item.precision("net_amount"),
											),
											"remarks": self.get("remarks") or _("Accounting Entry for Stock"),
											"cost_center": item.cost_center,
											"project": item.project or self.project,
											"party_type": "Supplier",
											"party": self.supplier
										},
										account_currency,
										item=item,
									)
								)
							else:
								gl_entries.append(
									self.get_gl_dict(
										{
											"account": item.expense_account,
											"against": self.supplier,
											"debit": warehouse_debit_amount,
											"debit_in_transaction_currency": flt(
												warehouse_debit_amount / self.conversion_rate,
												item.precision("net_amount"),
											),
											"remarks": self.get("remarks") or _("Accounting Entry for Stock"),
											"cost_center": item.cost_center,
											"project": item.project or self.project,
										},
										account_currency,
										item=item,
									)
								)

					# Amount added through landed-cost-voucher
					if landed_cost_entries:
						if (item.item_code, item.name) in landed_cost_entries:
							for account, base_amount in landed_cost_entries[
								(item.item_code, item.name)
							].items():
								gl_entries.append(
									self.get_gl_dict(
										{
											"account": account,
											"against": item.expense_account,
											"cost_center": item.cost_center,
											"remarks": self.get("remarks") or _("Accounting Entry for Stock"),
											"credit": flt(base_amount["base_amount"]),
											"credit_in_account_currency": flt(base_amount["amount"]),
											"credit_in_transaction_currency": item.net_amount,
											"project": item.project or self.project,
										},
										item=item,
									)
								)

					# sub-contracting warehouse
					if flt(item.rm_supp_cost):
						supplier_warehouse_account = warehouse_account[self.supplier_warehouse]["account"]
						if not supplier_warehouse_account:
							frappe.throw(
								_("Please set account in Warehouse {0}").format(self.supplier_warehouse)
							)
						gl_entries.append(
							self.get_gl_dict(
								{
									"account": supplier_warehouse_account,
									"against": item.expense_account,
									"cost_center": item.cost_center,
									"project": item.project or self.project,
									"remarks": self.get("remarks") or _("Accounting Entry for Stock"),
									"credit": flt(item.rm_supp_cost),
									"credit_in_transaction_currency": item.net_amount,
								},
								warehouse_account[self.supplier_warehouse]["account_currency"],
								item=item,
							)
						)

				else:
					expense_account = (
						item.expense_account
						if (not item.enable_deferred_expense or self.is_return)
						else item.deferred_expense_account
					)

					account_currency = get_account_currency(expense_account)
					amount, base_amount = self.get_amount_and_base_amount(item, None)

					if provisional_accounting_for_non_stock_items:
						self.make_provisional_gl_entry(gl_entries, item)

					if not self.is_internal_transfer():

						acc_doc = frappe.get_doc("Account", item.expense_account)

						total_taxes = 0
						for ri in self.taxes:
							if ri.category == "Valuation and Total" and "PPH 21" in ri.account_head:
								total_taxes += ri.tax_amount

						if acc_doc.account_type == "Payable":
							gl_entries.append(
								self.get_gl_dict(
									{
										"account": expense_account,
										"against": self.supplier,
										"debit": ((item.valuation_rate or item.rate) * item.qty)-total_taxes,
										"debit_in_transaction_currency": amount,
										"cost_center": item.cost_center,
										"project": item.project or self.project,
										"party_type": "Supplier",
										"party": self.supplier,
										"voucher_detail_no": item.name
									},
									account_currency,
									item=item,
								)
							)
						else:
							gl_entries.append(
								self.get_gl_dict(
									{
										"account": expense_account,
										"against": self.supplier,
										"debit": ((item.valuation_rate or item.rate) * item.qty)-total_taxes,
										"debit_in_transaction_currency": amount,
										"cost_center": item.cost_center,
										"project": item.project or self.project,
										"voucher_detail_no": item.name
									},
									account_currency,
									item=item,
								)
							)

						# check if the exchange rate has changed
						if item.get("purchase_receipt") and self.auto_accounting_for_stock:
							if (
								exchange_rate_map[item.purchase_receipt]
								and self.conversion_rate != exchange_rate_map[item.purchase_receipt]
								and item.net_rate == net_rate_map[item.pr_detail]
								and item.item_code in stock_items
							):
								discrepancy_caused_by_exchange_rate_difference = (
									item.qty * item.net_rate
								) * (exchange_rate_map[item.purchase_receipt] - self.conversion_rate)

								gl_entries.append(
									self.get_gl_dict(
										{
											"account": expense_account,
											"against": self.supplier,
											"debit": discrepancy_caused_by_exchange_rate_difference,
											"cost_center": item.cost_center,
											"project": item.project or self.project,
											"voucher_detail_no": item.name,
										},
										account_currency,
										item=item,
									)
								)
								gl_entries.append(
									self.get_gl_dict(
										{
											"account": self.get_company_default("exchange_gain_loss_account"),
											"against": self.supplier,
											"credit": discrepancy_caused_by_exchange_rate_difference,
											"cost_center": item.cost_center,
											"project": item.project or self.project,
											"voucher_detail_no": item.name,
										},
										account_currency,
										item=item,
									)
								)

			if item.is_fixed_asset and item.landed_cost_voucher_amount:
				self.update_gross_purchase_amount_for_linked_assets(item)

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
def get_all_training_event():
    return frappe.db.sql("""
        SELECT
            te.name,
            te.custom_posting_date,
            te.supplier,
			te.unit
        FROM `tabTraining Event` te
        WHERE
            te.docstatus = 1
            AND NOT EXISTS (
                SELECT 1
                FROM `tabPurchase Invoice` pi
                WHERE
                    pi.docstatus = 1
                    AND pi.document_type = 'Training Event'
                    AND pi.document_no = te.name
            )
        ORDER BY te.custom_posting_date DESC
    """, as_dict=True)

# @frappe.whitelist()
# def get_item_costing_in_training_events(training_events):
#   training_events = frappe.parse_json(training_events)
#   return frappe.db.sql("""
# 	SELECT
# 	i.name as item,
# 	i.item_name as item_code,
# 	i.stock_uom as stock_uom,
# 	SUM(tec.total_amount) as total_amount
# 	FROM `tabTraining Event Costing` as tec
# 	JOIN `tabExpense Claim Type` as ect ON ect.name = tec.expense_type
# 	JOIN `tabItem` as i ON i.name = "20102005"
# 	WHERE tec.parent IN %(training_events)s
# 	GROUP BY i.name, i.item_name, i.stock_uom;
#   """, {"training_events": tuple(training_events)}, as_dict=True)

@frappe.whitelist()
def get_item_costing_in_training_events(training_events):
    training_events = frappe.parse_json(training_events)

    return frappe.db.sql("""
        SELECT
            i.name AS item,
            i.item_name AS item_code,
            i.stock_uom,
            tec.total_amount,
			tec.expense_type
        FROM `tabTraining Event Costing` tec
        JOIN `tabItem` i
            ON i.name = "20102005"
        WHERE tec.parent IN %(training_events)s
    """, {
        "training_events": tuple(training_events)
    }, as_dict=True)


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

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_purchase_receipt_with_po(doctype, txt, searchfield, start, page_len, filters):
	"""
	Custom query untuk mendapatkan Purchase Receipt yang itemnya
	mengandung Purchase Order tertentu
	"""

	purchase_order = filters.get("purchase_order")
	company = filters.get("company")
	status_not_in = filters.get("status", ["Closed", "Completed", "Return Issued"])

	conditions = []
	values = []

	# Base conditions
	if company:
		conditions.append("pr.company = %s")
		values.append(company)

	conditions.append("pr.docstatus = 1")
	conditions.append("pr.is_return = 0")

	# Status filter
	if status_not_in:
		placeholders = ", ".join(["%s"] * len(status_not_in))
		conditions.append(f"pr.status NOT IN ({placeholders})")
		values.extend(status_not_in)

	# Search filter
	if txt:
		conditions.append("pr.name LIKE %s")
		values.append(f"%{txt}%")

	# Filter berdasarkan Purchase Order di items
	po_condition = ""
	if purchase_order:
		po_condition = """
		AND EXISTS (
			SELECT 1
			FROM `tabPurchase Receipt Item` pri
			WHERE pri.parent = pr.name
			AND pri.purchase_order = %s
		)
		"""
		values.append(purchase_order)

	where_clause = " AND ".join(conditions) if conditions else "1=1"

	query = f"""
		SELECT DISTINCT
			pr.name,
			pr.supplier,
			pr.posting_date,
			pr.grand_total
		FROM
			`tabPurchase Receipt` pr
		WHERE
			{where_clause}
			{po_condition}
		ORDER BY
			pr.posting_date DESC, pr.name DESC
		LIMIT
			{start}, {page_len}
	"""

	return frappe.db.sql(query, tuple(values))


@frappe.whitelist()
def get_purchase_receipts_by_po(purchase_order):
	"""
	Alternative method: Get list of Purchase Receipts containing specific PO
	Returns list of PR names
	"""

	if not purchase_order:
		return []

	pr_list = frappe.db.sql("""
		SELECT DISTINCT parent
		FROM `tabPurchase Receipt Item`
		WHERE purchase_order = %s
		AND docstatus = 1
	""", purchase_order, as_dict=1)

	return [pr.parent for pr in pr_list]

def get_or_create_cost_center(kode_vra, company):
    """
    Ambil Cost Center dengan nama = kode_vra untuk company terkait.
    Kalau belum ada (mis. kendaraan belum sempat membuat cost center-nya sendiri),
    buat otomatis mengikuti pola yang sama seperti Alat Berat Dan Kendaraan.
    """
    existing = frappe.db.get_value("Cost Center", {"cost_center_name": kode_vra, "company": company}, "name")
    if existing:
        return existing

    company_doc = frappe.get_cached_doc("Company", company)

    cc = frappe.new_doc("Cost Center")
    cc.cost_center_name = kode_vra
    cc.parent_cost_center = "VRA - {0}".format(company_doc.abbr)
    cc.company = company
    cc.is_group = 0
    cc.flags.ignore_permissions = True
    cc.insert()

    return cc.name