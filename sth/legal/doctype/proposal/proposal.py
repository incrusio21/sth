# Copyright (c) 2026 DAS and Contributors
# License: GNU General Public License v3. See license.txt


import json

import frappe
from frappe import _, msgprint
from frappe.desk.notifications import clear_doctype_notifications
from frappe.model.mapper import get_mapped_doc, map_docs
from frappe.model.workflow import get_workflow_name, is_transition_condition_satisfied
from frappe.utils import cint, cstr, flt, getdate, get_link_to_form, nowdate
from frappe.query_builder.functions import Sum

from erpnext.accounts.doctype.sales_invoice.sales_invoice import (
	update_linked_doc,
	validate_inter_company_party,
)
from erpnext.accounts.doctype.tax_withholding_category.tax_withholding_category import (
	get_party_tax_withholding_details,
)
from erpnext.accounts.party import complete_contact_details, get_party_account, get_party_account_currency, get_party_bank_account
from erpnext.accounts.doctype.payment_entry.payment_entry import get_bank_cash_account, set_paid_amount_and_received_amount, set_party_account, set_party_account_currency
from erpnext.buying.utils import check_on_hold_or_closed_status, validate_item_and_get_basic_data
from erpnext.controllers.buying_controller import BuyingController
from erpnext.manufacturing.doctype.blanket_order.blanket_order import (
	validate_against_blanket_order,
)
from erpnext.setup.doctype.item_group.item_group import get_item_group_defaults
from erpnext.stock.doctype.item.item import get_item_defaults, validate_end_of_life
from erpnext.stock.stock_balance import get_ordered_qty, update_bin_qty
from erpnext.stock.utils import get_bin
from erpnext.subcontracting.doctype.subcontracting_bom.subcontracting_bom import (
	get_subcontracting_boms_for_finished_goods,
)
from sth.legal import get_legal_settings

form_grid_templates = {"items": "templates/form_grid/item_grid.html"}


class Proposal(BuyingController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.status_updater = [
			{
				"source_dt": "Proposal Item",
				"target_dt": "Material Request Item",
				"join_field": "material_request_item",
				"target_field": "ordered_qty",
				"target_parent_dt": "Material Request",
				"target_parent_field": "per_ordered",
				"target_ref_field": "stock_qty",
				"source_field": "stock_qty",
				"percent_join_field": "material_request",
			}
		]

	def onload(self):
		supplier_tds = frappe.db.get_value("Supplier", self.supplier, "tax_withholding_category")
		self.set_onload("supplier_tds", supplier_tds)
		self.set_onload("can_update_items", True)
		# self.lm_processed_bapp()
	
	def lm_processed_bapp(self):
		from frappe.query_builder import functions as fn

		# Define DocTypes
		bapp_item = frappe.qb.DocType("BAPP Item")
		bapp = frappe.qb.DocType("BAPP")

		# Build query
		query = (
			frappe.qb.from_(bapp_item)
			.inner_join(bapp)
			.on(bapp.name == bapp_item.parent)
			.select(
				bapp_item.proposal_item,
				bapp_item.qty
			)
			.where(bapp_item.proposal == self.name)
			.where(fn.Extract("month", bapp.posting_date) == (getdate().month - 1))
			.groupby(bapp_item.proposal_item)
		)

		# Execute and convert to dict
		self.set_onload("lm_bapp", frappe._dict(query.run())) 
		
	def before_validate(self):
		self.set_has_unit_price_items()
		self.flags.allow_zero_qty = self.has_unit_price_items
	
	def validate(self):
		self.set_item_kegiatan_name()
		
		super().validate()

		self.set_status()

		# apply tax withholding only if checked and applicable
		# self.set_tax_withholding()

		self.validate_supplier()
		self.validate_capex()
		self.validate_schedule_date()
		validate_for_items(self)
		self.check_on_hold_or_closed_status()

		self.validate_uom_is_integer("uom", "qty")
		self.validate_uom_is_integer("stock_uom", "stock_qty")

		self.validate_with_previous_doc()
		self.validate_minimum_order_qty()
		validate_against_blanket_order(self)

		validate_inter_company_party(
			self.doctype, self.supplier, self.company, self.inter_company_order_reference
		)
		self.reset_default_field_value("set_warehouse", "items", "warehouse")

		self.set_project_name()
		self.set_retensi_or_term_value()
		
	def set_item_kegiatan_name(self):
		legal_item = get_legal_settings("default_item_code")

		for item in self.items:
			if item.item_code:
				continue

			if item.kegiatan:
				item.item_code = frappe.get_cached_value("Kegiatan", item.kegiatan, "item_code")
			
			if not item.item_code:
				item.item_code = legal_item 

	def validate_capex(self):
		if self.proposal_type not in ["Capex"]:
			self.asset_category = self.sub_asset_category = ""
		elif not (self.asset_category and self.sub_asset_category):
			frappe.throw("Please set Asset and Sub Asset Category first")

	def set_has_unit_price_items(self):
		"""
		If permitted in settings and any item has 0 qty, the PO has unit price items.
		"""
		if not frappe.db.get_single_value("Buying Settings", "allow_zero_qty_in_purchase_order"):
			return

		self.has_unit_price_items = any(
			not row.qty for row in self.get("items") if (row.item_code and not row.qty)
		)

	def validate_with_previous_doc(self):
		mri_compare_fields = [["project", "="], ["item_code", "="]]

		super().validate_with_previous_doc(
			{
				"Supplier Quotation": {
					"ref_dn_field": "supplier_quotation",
					"compare_fields": [["supplier", "="], ["company", "="], ["currency", "="]],
				},
				"Supplier Quotation Item": {
					"ref_dn_field": "supplier_quotation_item",
					"compare_fields": [
						["project", "="],
						["item_code", "="],
						["uom", "="],
						["conversion_factor", "="],
					],
					"is_child_table": True,
				},
				"Material Request": {
					"ref_dn_field": "material_request",
					"compare_fields": [["company", "="]],
				},
				"Material Request Item": {
					"ref_dn_field": "material_request_item",
					"compare_fields": mri_compare_fields,
					"is_child_table": True,
				},
			}
		)

		if cint(frappe.db.get_single_value("Buying Settings", "maintain_same_rate")):
			self.validate_rate_with_reference_doc(
				[["Supplier Quotation", "supplier_quotation", "supplier_quotation_item"]]
			)

		if not self.from_proposal:
			return
		
		self.compare_values(
			{"Proposal": [self.from_proposal]}, 
			[["supplier", "="], ["company", "="], ["currency", "="], ["need_project", "="]]
		)
		for d in self.items:
			self.compare_values(
				{"Proposal Item": [d.from_proposal_item]}, 
				[
					["project", "="],
					["item_code", "="],
					["uom", "="],
					["conversion_factor", "="],
				] , 
				d
			)

	def set_tax_withholding(self):
		if not self.apply_tds:
			return

		tax_withholding_details = get_party_tax_withholding_details(self, self.tax_withholding_category)

		if not tax_withholding_details:
			return

		accounts = []
		for d in self.taxes:
			if d.account_head == tax_withholding_details.get("account_head"):
				d.update(tax_withholding_details)
			accounts.append(d.account_head)

		if not accounts or tax_withholding_details.get("account_head") not in accounts:
			self.append("taxes", tax_withholding_details)

		to_remove = [
			d
			for d in self.taxes
			if not d.tax_amount and d.account_head == tax_withholding_details.get("account_head")
		]

		for d in to_remove:
			self.remove(d)

		# calculate totals again after applying TDS
		self.calculate_taxes_and_totals()

	def validate_supplier(self):
		prevent_po = frappe.db.get_value("Supplier", self.supplier, "prevent_pos")
		if prevent_po:
			standing = frappe.db.get_value("Supplier Scorecard", self.supplier, "status")
			if standing:
				frappe.throw(
					_("Proposals are not allowed for {0} due to a scorecard standing of {1}.").format(
						self.supplier, standing
					)
				)

		warn_po = frappe.db.get_value("Supplier", self.supplier, "warn_pos")
		if warn_po:
			standing = frappe.db.get_value("Supplier Scorecard", self.supplier, "status")
			frappe.msgprint(
				_(
					"{0} currently has a {1} Supplier Scorecard standing, and Proposals to this supplier should be issued with caution."
				).format(self.supplier, standing),
				title=_("Caution"),
				indicator="orange",
			)

		self.party_account_currency = get_party_account_currency("Supplier", self.supplier, self.company)

	def validate_minimum_order_qty(self):
		if not self.get("items"):
			return
		items = list(set(d.item_code for d in self.get("items")))

		itemwise_min_order_qty = frappe._dict(
			frappe.db.sql(
				"""select name, min_order_qty
			from tabItem where name in ({})""".format(", ".join(["%s"] * len(items))),
				items,
			)
		)

		itemwise_qty = frappe._dict()
		for d in self.get("items"):
			itemwise_qty.setdefault(d.item_code, 0)
			itemwise_qty[d.item_code] += flt(d.stock_qty)

		for item_code, qty in itemwise_qty.items():
			if flt(qty) < flt(itemwise_min_order_qty.get(item_code)):
				frappe.throw(
					_(
						"Item {0}: Ordered qty {1} cannot be less than minimum order qty {2} (defined in Item)."
					).format(item_code, qty, itemwise_min_order_qty.get(item_code))
				)

	def set_project_name(self):
		if not self.is_cwip:
			self.project_name = self.asset_category = self.sub_asset_category = ""
			return
		
		self.project_name = f"{self.asset_category}-{self.sub_asset_category}"
	
	def set_retensi_or_term_value(self):
		if not self.is_bapp_retensi:
			self.retensi = 0
		else:
			self.payment_schedule = []

	def get_schedule_dates(self):
		for d in self.get("items"):
			if d.material_request_item and not d.schedule_date:
				d.schedule_date = frappe.db.get_value(
					"Material Request Item", d.material_request_item, "schedule_date"
				)	

	# Check for Closed status
	def check_on_hold_or_closed_status(self):
		check_list = []
		for d in self.get("items"):
			if (
				d.meta.get_field("material_request")
				and d.material_request
				and d.material_request not in check_list
			):
				check_list.append(d.material_request)
				check_on_hold_or_closed_status("Material Request", d.material_request)

	def check_modified_date(self):
		mod_db = frappe.db.sql("select modified from `tabProposal` where name = %s", self.name)
		date_diff = frappe.db.sql(f"select '{mod_db[0][0]}' - '{cstr(self.modified)}' ")

		if date_diff and date_diff[0][0]:
			msgprint(
				_("{0} {1} has been modified. Please refresh.").format(self.doctype, self.name),
				raise_exception=True,
			)

	def update_status(self, status):
		self.check_modified_date()
		self.set_status(update=True, status=status)
		self.update_requested_qty()
		self.update_blanket_order()
		self.notify_update()
		clear_doctype_notifications(self)

	def on_submit(self):
		super().on_submit()

		self.update_prevdoc_status()

		self.validate_budget()

		frappe.get_doc("Authorization Control").validate_approving_authority(
			self.doctype, self.company, self.base_grand_total
		)

		self.update_blanket_order()

		update_linked_doc(self.doctype, self.name, self.inter_company_order_reference)

		self.update_previous_order()

	def on_cancel(self):
		self.ignore_linked_doctypes = (
			"GL Entry",
			"Payment Ledger Entry",
			"Unreconcile Payment",
			"Unreconcile Payment Entries",
		)

		super().on_cancel()

		self.check_on_hold_or_closed_status()

		self.db_set("status", "Cancelled")

		self.update_prevdoc_status()

		self.update_ordered_qty()

		self.update_blanket_order()

		self.update_previous_order(cancel=1)

	def update_previous_order(self, cancel=0):
		if not self.from_proposal:
			return
		
		# check jika proposal sudah memiliki revisi
		if not cancel and frappe.db.exists(
			"Proposal", 
			{"name": ["!=", self.name], "from_proposal": self.from_proposal, "docstatus": 1
		}):
			frappe.throw("Proposal already have Revisions")
			
		prev_doc = frappe.get_doc("Proposal", self.from_proposal)
		status = "Closed" if not cancel else "Draft"
		if prev_doc.docstatus == 1:
			prev_doc.update_status(status)
			prev_doc.update_blanket_order()

	def on_update(self):
		pass

	def update_receiving_percentage(self):
		total_qty, received_qty = 0.0, 0.0
		for item in self.items:
			received_qty += min(item.received_qty, item.qty)
			total_qty += item.qty
		if total_qty:
			self.db_set("per_received", flt(received_qty / total_qty) * 100, update_modified=False)
		else:
			self.db_set("per_received", 0, update_modified=False)

	def set_missing_values(self, for_validate=False):
		tds_category = frappe.db.get_value("Supplier", self.supplier, "tax_withholding_category")
		if tds_category and not for_validate:
			self.set_onload("supplier_tds", tds_category)

		self.supplier_address_active = frappe.db.get_value("Alamat dan PIC", {"parent": self.supplier, "status_pic": "Aktif"}, "alamat_pic")
		super().set_missing_values(for_validate)

def validate_for_items(doc) -> None:
	items = []
	for d in doc.get("items"):
		item = validate_item_and_get_basic_data(row=d)
		validate_end_of_life(d.item_code, item.end_of_life, item.disabled)

		items.append(cstr(d.item_code))

	if (
		items
		and len(items) != len(set(items))
		and not cint(frappe.db.get_single_value("Buying Settings", "allow_multiple_items") or 0)
	):
		frappe.throw(_("Same item cannot be entered multiple times."))

@frappe.whitelist()
def close_or_unclose_purchase_orders(names, status):
	if not frappe.has_permission("Purchase Order", "write"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	names = json.loads(names)
	for name in names:
		po = frappe.get_doc("Purchase Order", name)
		if po.docstatus == 1:
			if status == "Closed":
				if po.status not in ("Cancelled", "Closed") and (
					po.per_received < 100 or po.per_billed < 100
				):
					po.update_status(status)
			else:
				if po.status == "Closed":
					po.update_status("Draft")
			po.update_blanket_order()

	frappe.local.message_log = []

def set_missing_values(source, target):
	target.run_method("set_missing_values")
	target.run_method("calculate_taxes_and_totals")

@frappe.whitelist()
def make_purchase_invoice(source_name, target_doc=None):
	return get_mapped_purchase_invoice(source_name, target_doc)


@frappe.whitelist()
def make_purchase_invoice_from_portal(purchase_order_name):
	doc = get_mapped_purchase_invoice(purchase_order_name, ignore_permissions=True)
	if doc.contact_email != frappe.session.user:
		frappe.throw(_("Not Permitted"), frappe.PermissionError)
	doc.save()
	frappe.db.commit()
	frappe.response["type"] = "redirect"
	frappe.response.location = "/purchase-invoices/" + doc.name


def get_mapped_purchase_invoice(source_name, target_doc=None, ignore_permissions=False):
	term = frappe.flags.args.term
	portion = frappe.db.get_value("Payment Schedule", term, "invoice_portion")
	def postprocess(source, target):
		target.flags.ignore_permissions = ignore_permissions
		set_missing_values(source, target)

		# set tax_withholding_category from Purchase Order
		# if source.apply_tds and source.tax_withholding_category and target.apply_tds:
		# 	target.tax_withholding_category = source.tax_withholding_category

		# Get the advance paid Journal Entries in Purchase Invoice Advance
		if target.get("allocate_advances_automatically"):
			target.set_advances()
		
		target.invoice_type = "SPK"
		target.term_detail = term
		target.set_payment_schedule()
		target.credit_to = get_party_account("Supplier", source.supplier, source.company)

	def update_item(obj, target, source_parent):
		target.qty = flt(obj.qty * portion / 100)
		target.amount = flt(obj.rate) * flt(target.qty)
		target.base_amount = target.amount * flt(source_parent.conversion_rate)

		item = get_item_defaults(target.item_code, source_parent.company)
		item_group = get_item_group_defaults(target.item_code, source_parent.company)
		target.cost_center = (
			obj.cost_center
			or frappe.db.get_value("Project", obj.project, "cost_center")
			or item.get("buying_cost_center")
			or item_group.get("buying_cost_center")
		)

	fields = {
		"Proposal": {
			"doctype": "Purchase Invoice",
			"field_map": {
				"party_account_currency": "party_account_currency",
				"supplier_warehouse": "supplier_warehouse",
			},
			"field_no_map": ["payment_terms_template"],
			"validation": {
				"docstatus": ["=", 1],
			},
		},
		"Proposal Item": {
			"doctype": "Purchase Invoice Item",
			"field_map": {
				"name": "proposal_detail",
				"parent": "proposal",
				"material_request": "material_request",
				"material_request_item": "material_request_item",
				"wip_composite_asset": "wip_composite_asset",
			},
			"postprocess": update_item,
			"condition": lambda doc: (doc.base_amount == 0 or abs(doc.billed_amt) < abs(doc.amount)),
		},
		"Purchase Taxes and Charges": {"doctype": "Purchase Taxes and Charges", "reset_value": True},
	}

	doc = get_mapped_doc(
		"Proposal",
		source_name,
		fields,
		target_doc,
		postprocess,
		ignore_permissions=ignore_permissions,
	)

	return doc


def get_list_context(context=None):
	from erpnext.controllers.website_list_for_contact import get_list_context

	list_context = get_list_context(context)
	list_context.update(
		{
			"show_sidebar": True,
			"show_search": True,
			"no_breadcrumbs": True,
			"title": _("Proposals"),
		}
	)
	return list_context

@frappe.whitelist()
def update_status(status, name):
	po = frappe.get_doc("Proposal", name)
	po.update_status(status)

@frappe.whitelist()
def get_kegiatan_item(kegiatan):
    keg_doc = frappe.get_cached_doc("Kegiatan", kegiatan)

    return {
		"kegiatan_name": keg_doc.nm_kgt,
        "uom": keg_doc.uom
    }

@frappe.whitelist()
def update_progress_item(parent_doctype, trans_items, parent_doctype_name, child_docname="items"):
	def check_doc_permissions(doc, perm_type="create"):
		try:
			doc.check_permission(perm_type)
		except frappe.PermissionError:
			actions = {"create": "add", "write": "update"}

			frappe.throw(
				_("You do not have permissions to {} items in a {}.").format(
					actions[perm_type], parent_doctype
				),
				title=_("Insufficient Permissions"),
			)

	def validate_workflow_conditions(doc):
		workflow = get_workflow_name(doc.doctype)
		if not workflow:
			return

		workflow_doc = frappe.get_doc("Workflow", workflow)
		current_state = doc.get(workflow_doc.workflow_state_field)
		roles = frappe.get_roles()

		transitions = []
		for transition in workflow_doc.transitions:
			if transition.next_state == current_state and transition.allowed in roles:
				if not is_transition_condition_satisfied(transition, doc):
					continue
				transitions.append(transition.as_dict())

		if not transitions:
			frappe.throw(
				_("You are not allowed to update as per the conditions set in {} Workflow.").format(
					get_link_to_form("Workflow", workflow)
				),
				title=_("Insufficient Permissions"),
			)

	def validate_progress(child_item, new_data):
		real_progress = new_data.get("progress_received") + child_item.received_qty
		if flt(real_progress) > flt(child_item.qty):
			frappe.throw(_("Cannot set Progress more than quantity"))

	data = json.loads(trans_items)
	any_update = False
	parent = frappe.get_doc(parent_doctype, parent_doctype_name)
	check_doc_permissions(parent, "write")

	for d in data:
		check_doc_permissions(parent, "write")
		child_item = parent.get(child_docname, {"name": d.get("docname")})[0]

		prev_progress_received, new_progress_received = flt(child_item.get("progress_received")), flt(d.get("progress_received"))

		progress_received_unchanged = prev_progress_received == new_progress_received
		if (
			progress_received_unchanged
		):
			continue

		validate_progress(child_item, d)

		child_item.progress_received = flt(d.get("progress_received"))

		any_update = True

	if any_update:
		parent.flags.ignore_validate_update_after_submit = True
		parent.save()

	parent.reload()
	validate_workflow_conditions(parent)

	# update percentase task
	order_item, cond = [], ""   
	for item in parent.items:
		real_progress = item.progress_received + child_item.received_qty

		cond += """ WHEN (proposal = {} and proposal_item = {}) THEN {}
			""".format(
			frappe.db.escape(parent.name),
			frappe.db.escape(item.name),
			flt(real_progress/item.qty*100),
		)

		order_item.append(item.name)

	if order_item:
		frappe.db.sql(
			""" UPDATE `tabTask`
			SET
				progress = CASE {} END
			WHERE
				proposal_item in %(po_details)s """.format(cond),
			{"po_details": order_item}
		)

def get_proposal_invoice(document_no, as_dict=True):
	
	parent = frappe.qb.DocType("Purchase Invoice")
	child = frappe.qb.DocType("Purchase Invoice Item")

	inv_out = (
		frappe.qb.from_(parent)
		.inner_join(child)
		.on(parent.name == child.parent)
		.select(
			parent.name,
			parent.grand_total,
			parent.outstanding_amount,
			parent.retensi_amount,
			parent.credit_to,
			parent.cost_center,

		)
		.where(
			(child.proposal == document_no) &
			(parent.docstatus == 1)
		)
		.groupby(parent.name)
		.for_update()
	).run(as_dict=as_dict)

	return inv_out

@frappe.whitelist()
def update_retensi_status(document_no, status):
	retensi_paid = 1 if status == "Approve" else 0
	frappe.db.set_value("Proposal", document_no, "retensi_paid", retensi_paid)

	inv_list = []
	for inv in get_proposal_invoice(document_no):
		if inv.outstanding_amount < inv.retensi_amount:
			frappe.throw(f"Can't update Retensi status. because Outstanding already less than Retensi Amount")

		inv_list.append(inv.name)

	frappe.db.set_value("Purchase Invoice", {"name": ["in", inv_list]}, "retensi_paid", retensi_paid)

@frappe.whitelist()
def get_payment_entry(document_no):
	doc = frappe.get_doc("Proposal", document_no)

	in_list = get_proposal_invoice(document_no)
	
	pe = frappe.new_doc("Payment Entry")

	# set reference first
	outstanding_amount = 0
	for inv in in_list:
		pe.append(
			"references",
			{
				"reference_doctype": "Purchase Invoice",
				"reference_name": inv.name,
				"bill_no": doc.get("bill_no"),
				"due_date": doc.get("due_date"),
				"total_amount": inv.grand_total,
				"outstanding_amount": inv.outstanding_amount,
				"allocated_amount": inv.outstanding_amount,
			},
		)

		outstanding_amount += inv.outstanding_amount
		party_account = inv.credit_to
	
	party_account_currency = set_party_account_currency("Proposal", party_account, doc)

	bank = get_bank_cash_account(doc, None)

	paid_amount, received_amount = set_paid_amount_and_received_amount(
		"Purchase Invoice", party_account_currency, bank, outstanding_amount, "Pay", None, doc
	)
	
	pe.payment_type = "Pay"
	pe.company = doc.company
	# pe.cost_center = doc.get("cost_center")
	pe.posting_date = nowdate()
	pe.reference_date = getdate(None)
	pe.party_type = "Supplier"
	pe.party = doc.supplier
	pe.contact_person = doc.get("contact_person")
	complete_contact_details(pe)
	pe.ensure_supplier_is_not_blocked()

	pe.paid_from = bank.account
	pe.paid_to = party_account
	pe.paid_from_account_currency = (
		bank.account_currency
	)
	pe.paid_to_account_currency = party_account_currency
	pe.paid_from_account_type = frappe.db.get_value("Account", pe.paid_from, "account_type")
	pe.paid_to_account_type = frappe.db.get_value("Account", pe.paid_to, "account_type")
	pe.paid_amount = paid_amount
	pe.received_amount = received_amount
	pe.letter_head = doc.get("letter_head")
	pe.bank_account = frappe.db.get_value(
		"Bank Account", {"is_company_account": 1, "is_default": 1, "company": doc.company}, "name"
	)
	# get first non-empty project from items

	if pe.party_type in ["Customer", "Supplier"]:
		bank_account = get_party_bank_account(pe.party_type, pe.party)
		pe.set("party_bank_account", bank_account)
		pe.set_bank_account_data()


	pe.setup_party_account_field()
	pe.set_missing_values()
	pe.set_missing_ref_details()

	# update_accounting_dimensions(pe, doc)

	# if party_account and bank:
	# 	if discount_amount:
	# 		base_total_discount_loss = 0
	# 		if frappe.db.get_single_value("Accounts Settings", "book_tax_discount_loss"):
	# 			base_total_discount_loss = split_early_payment_discount_loss(pe, doc, valid_discounts)

	# 		set_pending_discount_loss(
	# 			pe, doc, discount_amount, base_total_discount_loss, party_account_currency
	# 		)

	# 	pe.set_exchange_rate(ref_doc=doc)
	# 	pe.set_amounts()

	return pe

@frappe.whitelist()
def make_proposal_revision(source_name, target_doc=None):
	has_unit_price_items = frappe.db.get_value("Proposal", source_name, "has_unit_price_items")

	def set_missing_values(source, target):
		# pastikan po lama sudah memiliki project
		if not frappe.db.exists("Project", {"proposal": source.name}):
			frappe.throw("Please create a Project for the Proposal before making revisions")
		
		target.total = 0
		target.run_method("set_missing_values")
		target.run_method("calculate_taxes_and_totals")

		
	def is_unit_price_row(source):
		return has_unit_price_items and source.qty == 0

	def update_item(obj, target, source_parent):
		target.qty = flt(obj.qty) if is_unit_price_row(obj) else flt(obj.qty) - flt(obj.received_qty)
		target.stock_qty = (flt(obj.qty) - flt(obj.received_qty)) * flt(obj.conversion_factor)
		target.amount = (flt(obj.qty) - flt(obj.received_qty)) * flt(obj.rate)
		target.base_amount = (
			(flt(obj.qty) - flt(obj.received_qty)) * flt(obj.rate) * flt(source_parent.conversion_rate)
		)

	doc = get_mapped_doc(
		"Proposal",
		source_name,
		{
			"Proposal": {
				"doctype": "Proposal",
				"field_map": {
					"supplier_warehouse": "supplier_warehouse",
					"name": "from_order"
				},
				"validation": {
					"docstatus": ["=", 1],
				},
			},
			"Proposal Item": {
				"doctype": "Proposal Item",
				"field_map": {
					"name": "from_order_item",
					"material_request": "material_request",
					"material_request_item": "material_request_item",
					"sales_order": "sales_order",
					"sales_order_item": "sales_order_item",
					"wip_composite_asset": "wip_composite_asset",
				},
				"postprocess": update_item,
				"condition": lambda doc: (
					True if is_unit_price_row(doc) else abs(doc.received_qty) < abs(doc.qty)
				)
				and doc.delivered_by_supplier != 1,
			},
			"Purchase Taxes and Charges": {"doctype": "Purchase Taxes and Charges", "reset_value": True},
		},
		target_doc,
		set_missing_values,
	)

	return doc

@frappe.whitelist()
def make_bapp(source_name, target_doc=None):
	from sth.legal.custom.tax_validation import validate_custom_tax

	has_unit_price_items = frappe.db.get_value("Proposal", source_name, "has_unit_price_items")
	spk = frappe.db.get_value("Project", {"proposal": source_name, "status": ["!=", "Cancelled"]}, "name")
	if not spk:
		frappe.throw(f"Create SPK for {source_name} first")

	def set_missing_values(source, target):
		target.project = spk

		target.run_method("set_missing_values")
		target.run_method("calculate_taxes_and_totals")
		validate_custom_tax(target)
		
	def update_item(obj, target, source_parent):
		target.qty = flt(obj.progress_received)
		target.stock_qty = flt(obj.progress_received) * flt(obj.conversion_factor)
		target.amount = flt(obj.progress_received) * flt(obj.rate)
		target.base_amount = (
			flt(obj.progress_received) * flt(obj.rate) * flt(source_parent.conversion_rate)
		)

	doc = get_mapped_doc(
		"Proposal",
		source_name,
		{
			"Proposal": {
				"doctype": "BAPP",
				"field_map": {
					"supplier_warehouse": "supplier_warehouse",
					"retensi": "retensi",
					"is_bapp_retensi": "is_bapp_retensi"
				},
				"validation": {
					"docstatus": ["=", 1],
				},
			},
			"Proposal Item": {
				"doctype": "BAPP Item",
				"field_map": {
					"name": "proposal_item",
					"parent": "proposal",
				},
				"postprocess": update_item,
				"condition": lambda doc: doc.progress_received > 0
				and doc.delivered_by_supplier != 1,
			},
			"Purchase Taxes and Charges": {"doctype": "Purchase Taxes and Charges", "reset_value": True},
		},
		target_doc,
		set_missing_values,
	)

	return doc

@frappe.whitelist()
def make_invoice(source_name, target_doc=None):
	from sth.legal.custom.tax_validation import validate_custom_tax

	has_unit_price_items = frappe.db.get_value("Proposal", source_name, "has_unit_price_items")
	spk = frappe.db.get_value("Project", {"proposal": source_name, "status": ["!=", "Cancelled"]}, "name")
	if not spk:
		frappe.throw(f"Create SPK for {source_name} first")

	def set_missing_values(source, target):
		target.project = spk

		target.run_method("set_missing_values")
		target.run_method("calculate_taxes_and_totals")
		validate_custom_tax(target)
		
	def update_item(obj, target, source_parent):
		target.qty = flt(obj.progress_received)
		target.stock_qty = flt(obj.progress_received) * flt(obj.conversion_factor)
		target.amount = flt(obj.progress_received) * flt(obj.rate)
		target.base_amount = (
			flt(obj.progress_received) * flt(obj.rate) * flt(source_parent.conversion_rate)
		)

	doc = get_mapped_doc(
		"Proposal",
		source_name,
		{
			"Proposal": {
				"doctype": "BAPP",
				"field_map": {
					"supplier_warehouse": "supplier_warehouse",
					"retensi": "retensi",
					"is_bapp_retensi": "is_bapp_retensi"
				},
				"validation": {
					"docstatus": ["=", 1],
				},
			},
			"Proposal Item": {
				"doctype": "BAPP Item",
				"field_map": {
					"name": "proposal_item",
					"parent": "proposal",
				},
				"postprocess": update_item,
				"condition": lambda doc: doc.progress_received > 0
				and doc.delivered_by_supplier != 1,
			},
			"Purchase Taxes and Charges": {"doctype": "Purchase Taxes and Charges", "reset_value": True},
		},
		target_doc,
		set_missing_values,
	)

	return doc