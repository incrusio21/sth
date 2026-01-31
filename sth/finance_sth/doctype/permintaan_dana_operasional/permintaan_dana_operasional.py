# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.model.mapper import get_mapped_doc

from sth.finance_sth.doctype.pdo_bahan_bakar_vtwo.pdo_bahan_bakar_vtwo import process_pdo_bahan_bakar
from sth.finance_sth.doctype.pdo_perjalanan_dinas_vtwo.pdo_perjalanan_dinas_vtwo import process_pdo_perjalanan_dinas
from sth.finance_sth.doctype.pdo_kas_vtwo.pdo_kas_vtwo import process_pdo_kas
from sth.finance_sth.doctype.pdo_dana_cadangan_vtwo.pdo_dana_cadangan_vtwo import process_pdo_dana_cadangan
from sth.finance_sth.doctype.pdo_non_pdo_vtwo.pdo_non_pdo_vtwo import process_pdo_non_pdo

PROCESSORS_INSERT = {
	"Bahan Bakar": process_pdo_bahan_bakar,
	"Perjalanan Dinas": process_pdo_perjalanan_dinas,
	"Kas": process_pdo_kas,
	"Dana Cadangan": process_pdo_dana_cadangan,
	"NON PDO": process_pdo_non_pdo,
}
pdo_categories = ["Bahan Bakar", "Perjalanan Dinas", "Kas", "Dana Cadangan", "NON PDO"]

class PermintaanDanaOperasional(Document):
	def validate(self):
		self.update_pdo_default_account()
		self.validate_child_tables()

	def update_pdo_default_account(self):
		if not self.bahan_bakar_debit_to:
			self.bahan_bakar_debit_to = frappe.get_doc("Company", self.company).default_pdo_bahan_bakar_account

		
	def on_update(self):
		self.process_data_to_insert_vtwo()

	def before_submit(self):
		self.submit_pdo_vtwo()

	def before_cancel(self):
		self.cancel_pdo_vtwo()

	def on_trash(self):
		self.delete_pdo_vtwo()

	def process_data_to_insert_vtwo(self):
		for pdo in pdo_categories:
			fieldname = pdo.lower().replace(" ", "_")

			if not self.get(f"pdo_{fieldname}") and not self.get(f"{fieldname}_transaction_number"):
				continue
				
			data = {
				"grand_total": self.get(f"grand_total_{fieldname}"),
				"outstanding_amount": self.get(f"outstanding_amount_{fieldname}"),
				"credit_to": self.get(f"{fieldname}_credit_to"),
				"reference_doc": "Permintaan Dana Operasional",
				"reference_name": self.name,
				"employee": frappe.db.get_single_value("Payment Settings", "internal_employee"),
				"cost_center": self.get(f"{fieldname}_cost_center"),
				"company": self.company,
				"unit": self.unit,
				"posting_date": self.posting_date,
				"required_by": self.required_by,
			}

			if pdo == "Bahan Bakar":
				data.update({"debit_to": self.get(f"{fieldname}_debit_to")})
			
			childs = self.get(f"pdo_{fieldname}")
			
			handlers = PROCESSORS_INSERT.get(pdo)
			if handlers:
				handlers(data, childs)
	
	def submit_pdo_vtwo(self):
		for pdo in pdo_categories:
			fieldname = pdo.lower().replace(" ", "_")

			if self.get(f"pdo_{fieldname}") and self.get(f"{fieldname}_transaction_number") and self.get(f"grand_total_{fieldname}") > 0:
				doctype_vtwo = f"PDO {pdo} Vtwo"
				docname_vtwo = self.get(f"{fieldname}_transaction_number")
				doc = frappe.get_doc(doctype_vtwo, docname_vtwo)
				doc.submit()
	
	def cancel_pdo_vtwo(self):
		for pdo in pdo_categories:
			fieldname = pdo.lower().replace(" ", "_")

			if self.get(f"pdo_{fieldname}") and self.get(f"{fieldname}_transaction_number") and self.get(f"grand_total_{fieldname}") > 0:
				doctype_vtwo = f"PDO {pdo} Vtwo"
				docname_vtwo = self.get(f"{fieldname}_transaction_number")
				doc = frappe.get_doc(doctype_vtwo, docname_vtwo)
				doc.cancel()
	
	def delete_pdo_vtwo(self):
		for pdo in pdo_categories:
			fieldname = pdo.lower().replace(" ", "_")

			if self.get(f"pdo_{fieldname}") and self.get(f"{fieldname}_transaction_number"):
				doctype_vtwo = f"PDO {pdo} Vtwo"
				docname_vtwo = self.get(f"{fieldname}_transaction_number")
				doc = frappe.get_doc(doctype_vtwo, docname_vtwo)
				doc.delete()
	
	def validate_child_tables(self):
		validation_map = {
			"pdo_bahan_bakar": ["plafon", "unit_price", "revised_plafon", "revised_unit_price"],
			"pdo_perjalanan_dinas": ["plafon", "hari_dinas", "revised_plafon", "revised_duty_day"],
			"pdo_kas": ["qty", "price", "revised_qty", "revised_price"],
			"pdo_dana_cadangan": ["amount", "revised_amount"],
			"pdo_non_pdo": ["qty", "price", "revised_qty", "revised_price"],
		}

		for pdo in pdo_categories:
			fieldname = pdo.lower().replace(" ", "_")

			if not self.get(f"pdo_{fieldname}") and not self.get(f"{fieldname}_transaction_number"):
				continue
			for row in self.get(f"pdo_{fieldname}"):
				for valid in validation_map[f"pdo_{fieldname}"]:
					if row.get(valid) > 0:
						continue
					msg = f"Pada Tabel {pdo} baris ke {row.idx} field currency atau angka harus lebih besar dari 0"
					frappe.throw(msg)

@frappe.whitelist()
def filter_type(doctype, txt, searchfield, start, page_len, filters):
	ect = frappe.qb.DocType("Expense Claim Type")
	eca = frappe.qb.DocType("Expense Claim Account")
	
	query = (
		frappe.qb.from_(ect)
		.select(ect.name.as_('value'))
		.inner_join(eca)
		.on(
			(ect.name == eca.parent) &
			(ect.custom_routine_type == filters.get('routine_type')) &
			(ect.custom_pdo_type == filters.get('pdo_type'))
		)
		.where(
			(eca.company == filters.get('company')) &
			(ect.name.like(f'%{txt}%'))
		)
	)

	return query.run()

@frappe.whitelist()
def get_expense_account(company, parent):
	default_account = frappe.db.get_value("Expense Claim Account", {
		"company": company,
		"parent": parent
	}, "default_account")
	
	return default_account

@frappe.whitelist()
def filter_fund_type(doctype, txt, searchfield, start, page_len, filters):
	account = frappe.qb.DocType("Account")
	account_type = list(["Cash", "Bank"])
	query = (
		frappe.qb.from_(account)
		.select(account.name.as_('value'))
		.where(
			(account.company == filters.get('company')) &
			(account.account_type.isin(account_type))
		)
	)

	return query.run()

@frappe.whitelist()
def create_payment_voucher(source_name, target_doc=None):
	
	def validate_source(source):
		if source.payment_voucher:
			frappe.throw(_("Payment Voucher already created: {0}").format(source.payment_voucher))
	
	def set_missing_values(source, target):
		unit_doc = frappe.get_doc("Unit", source.unit)
		if not unit_doc.bank_account:
			frappe.throw(_("Bank Account not set for Unit: {0}").format(source.unit))
		
		target.paid_to = unit_doc.bank_account
		target.payment_type = "Internal Transfer"
		target.paid_from = "1111001 - KAS HO - TML"
		
		total_amount = (
			(source.grand_total_bahan_bakar or 0) +
			(source.grand_total_perjalanan_dinas or 0) +
			(source.grand_total_kas or 0) +
			(source.grand_total_dana_cadangan or 0) +
			(source.grand_total_non_pdo or 0)
		)
		
		if total_amount <= 0:
			frappe.throw(_("Total amount must be greater than zero"))
		
		target.paid_amount = total_amount
		target.received_amount = total_amount
		target.posting_date = frappe.utils.today()
		target.source_exchange_rate = 1
		target.paid_from_account_currency = "IDR"
		target.paid_to_account_currency = "IDR"
		target.remarks = _("Payment for Permintaan Dana Operasional {0}").format(source.name)
	
	source_doc = frappe.get_doc("Permintaan Dana Operasional", source_name)
	validate_source(source_doc)
	
	doclist = get_mapped_doc(
		"Permintaan Dana Operasional",
		source_name,
		{
			"Permintaan Dana Operasional": {
				"doctype": "Payment Entry",
				"field_map": {
					"name": "permintaan_dana_operasional",
					"unit": "unit",
					"company": "company"
				}
			}
		},
		target_doc,
		set_missing_values
	)
	
	return doclist

@frappe.whitelist()
def create_payment_voucher_kas(source_name, tipe_pdo, target_doc=None):
	"""Create Payment Voucher Kas from Permintaan Dana Operasional"""
	
	# Map tipe_pdo to child table and field mappings
	tipe_mapping = {
		'Bahan Bakar': {
			'child_table': 'pdo_bahan_bakar',
			'account_field': 'bahan_bakar_debit_to',
			'employee_field': 'employee',
			'amount_field': 'revised_price_total'
		},
		'Perjalanan Dinas': {
			'child_table': 'pdo_perjalanan_dinas',
			'account_field': 'perjalanan_dinas_debit_to',
			'employee_field': 'employee',
			'amount_field': 'revised_price_total'
		},
		'Kas': {
			'child_table': 'pdo_kas',
			'account_field': 'kas_debit_to',
			'employee_field': 'employee',
			'amount_field': 'revised_price_total'
		},
		'Dana Cadangan': {
			'child_table': 'pdo_dana_cadangan',
			'account_field': 'dana_cadangan_debit_to',
			'employee_field': 'employee',
			'amount_field': 'revised_price_total'
		}
	}
	
	if tipe_pdo not in tipe_mapping:
		frappe.throw(_("Invalid Tipe PDO selected"))
	
	mapping = tipe_mapping[tipe_pdo]
	child_table_name = mapping['child_table']
	account_field = mapping['account_field']
	employee_field = mapping['employee_field']
	amount_field = mapping['amount_field']
	
	def set_missing_values(source, target):
		# Get Payment Voucher to fetch paid_to account
		if not source.payment_voucher:
			frappe.throw(_("Payment Voucher not found for this PDO"))
		
		payment_voucher = frappe.get_doc("Payment Entry", source.payment_voucher)
		
		# Set basic fields
		target.company = source.company
		target.unit = source.unit
		target.currency = "IDR"
		target.exchange_rate = 1
		target.transaction_type = "Keluar"
		
		# Set account from source based on tipe_pdo
		if hasattr(source, account_field) and getattr(source, account_field):
			target.account = getattr(source, account_field)
		else:
			frappe.throw(_("Account field {0} not found in source document").format(account_field))
		
		# Set credit_to from Payment Voucher's paid_to
		target.credit_to = payment_voucher.paid_to
		
		# Clear any existing child table rows
		target.payment_voucher_kas_pdo = []
		
		# Get child table data
		child_data = getattr(source, child_table_name, [])
		
		if not child_data:
			frappe.throw(_("No data found in {0} table").format(tipe_pdo))
		
		# Add rows to payment_voucher_kas_pdo table
		for row in child_data:
			employee = getattr(row, employee_field, None) if hasattr(row, employee_field) else None
			amount = getattr(row, amount_field, 0) if hasattr(row, amount_field) else 0
			
			target.append('payment_voucher_kas_pdo', {
				'no_pdo': source.name,
				'tipe_pdo': tipe_pdo,
				'penerima': employee,
				'total': amount,
				'pdo_child_name': row.name
			})
	
	# Map document
	doclist = get_mapped_doc(
		"Permintaan Dana Operasional",
		source_name,
		{
			"Permintaan Dana Operasional": {
				"doctype": "Payment Voucher Kas",
				"field_map": {
					"name": "permintaan_dana_operasional",
					"company": "company",
					"unit": "unit"
				}
			}
		},
		target_doc,
		set_missing_values
	)
	
	return doclist