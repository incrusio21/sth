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

		
	# def on_update(self):
	# 	self.process_data_to_insert_vtwo()

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
			
			if self.get(f"pdo_{fieldname}") and self.get(f"{fieldname}_transaction_number"):
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
				print(str(pdo))
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
					if row.get(valid):
						if row.get(valid) > 0:
							continue
						msg = f"Pada Tabel {pdo} baris ke {row.idx} field currency atau angka harus lebih besar dari 0"
						frappe.throw(msg)

@frappe.whitelist()
def filter_type(doctype, txt, searchfield, start, page_len, filters):
	ect = frappe.qb.DocType("Expense Claim Type")
	eca = frappe.qb.DocType("Expense Claim Account")
	
	# query = (
	# 	frappe.qb.from_(ect)
	# 	.select(ect.name.as_('value'))
	# 	.inner_join(eca)
	# 	.on(
	# 		(ect.name == eca.parent) &
	# 		(ect.custom_routine_type == filters.get('routine_type')) 
	# 	)
	# 	.where(
	# 		(eca.company == filters.get('company')) &
	# 		(ect.name.like(f"%{txt}%"))  
	# 	)
	# )
	if filters.get("pdo_type"):
		query = (
			frappe.qb.from_(ect)
			.select(ect.name.as_('value'))
			.inner_join(eca)
			.on(
				(ect.name == eca.parent) 
			)
			.where(
				(eca.company == filters.get('company')) &
				(ect.name.like(f"%{txt}%"))  &
				(ect.custom_pdo_type == filters.get("pdo_type"))  
			)
		)
	else:
		query = (
			frappe.qb.from_(ect)
			.select(ect.name.as_('value'))
			.inner_join(eca)
			.on(
				(ect.name == eca.parent) 
			)
			.where(
				(eca.company == filters.get('company')) &
				(ect.name.like(f"%{txt}%"))  
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
			(account.disabled == 0) &
			(account.account_type.isin(account_type)) &
			(account.name.like(f"%{txt}%"))  
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
			'debit_account_field': None,  # Uses header field instead
			'header_debit_field': 'bahan_bakar_debit_to',  # Account at header level
			'employee_field': 'employee',
			'amount_field': 'revised_price_total',
			'grand_total_field': 'grand_total_bahan_bakar',
			'outstanding_field': 'outstanding_amount_bahan_bakar'
		},
		'Perjalanan Dinas': {
			'child_table': 'pdo_perjalanan_dinas',
			'debit_account_field': 'debit_to',  # Field in child table
			'header_debit_field': None,  # No header field
			'employee_field': 'employee',
			'amount_field': 'revised_total',
			'grand_total_field': 'grand_total_perjalanan_dinas',
			'outstanding_field': 'outstanding_amount_perjalanan_dinas'
		},
		'Kas': {
			'child_table': 'pdo_kas',
			'debit_account_field': 'debit_to',  # Field in child table
			'header_debit_field': None,
			'employee_field': 'employee',
			'amount_field': 'revised_total',
			'grand_total_field': 'grand_total_kas',
			'outstanding_field': 'outstanding_amount_kas'
		},
		'Dana Cadangan': {
			'child_table': 'pdo_dana_cadangan',
			'debit_account_field': 'fund_type',  # Field in child table
			'header_debit_field': None,
			'employee_field': 'employee',
			'amount_field': 'revised_amount',
			'grand_total_field': 'grand_total_dana_cadangan',
			'outstanding_field': 'outstanding_amount_dana_cadangan'
		}
	}
	
	if tipe_pdo not in tipe_mapping:
		frappe.throw(_("Invalid Tipe PDO selected"))
	
	mapping = tipe_mapping[tipe_pdo]
	child_table_name = mapping['child_table']
	debit_account_field = mapping['debit_account_field']
	header_debit_field = mapping['header_debit_field']
	employee_field = mapping['employee_field']
	amount_field = mapping['amount_field']
	outstanding_field = mapping['outstanding_field']

	source_doc = frappe.get_doc("Permintaan Dana Operasional", source_name)
	outstanding_amount = getattr(source_doc, outstanding_field, 0)
	
	if outstanding_amount <= 0:
		frappe.throw(_("{0} has been fully paid. Outstanding amount: {1}").format(
			tipe_pdo, 
			frappe.format_value(outstanding_amount, {'fieldtype': 'Currency'})
		))
	
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
		target.naming_series = "PVK-"
		
		# Set credit_to from Payment Voucher's paid_to (this is the bank account)
		target.credit_to = payment_voucher.paid_to
		
		# Clear any existing child table rows
		target.payment_voucher_kas_pdo = []
		
		# Get child table data
		child_data = getattr(source, child_table_name, [])
		
		if not child_data:
			frappe.throw(_("No data found in {0} table").format(tipe_pdo))
		
		# For Bahan Bakar, get debit account from header
		if header_debit_field:
			header_debit_account = getattr(source, header_debit_field, None)
			if not header_debit_account:
				frappe.throw(_("Debit account field {0} not found in source document").format(header_debit_field))
		
		# Add rows to payment_voucher_kas_pdo table
		for row in child_data:
			employee = getattr(row, employee_field, None) if hasattr(row, employee_field) else None
			amount = getattr(row, amount_field, 0) if hasattr(row, amount_field) else 0
			
			# Determine debit account
			if header_debit_field:
				# Use header field (for Bahan Bakar)
				debit_account = header_debit_account
			else:
				# Use child table field (for other types)
				debit_account = getattr(row, debit_account_field, None) if hasattr(row, debit_account_field) else None
				if not debit_account:
					frappe.throw(_("Debit account not found for row {0} in {1}").format(row.idx, tipe_pdo))
			
			target.append('payment_voucher_kas_pdo', {
				'no_pdo': source.name,
				'tipe_pdo': tipe_pdo,
				'penerima': employee,
				'total': amount,
				'debit_to': debit_account,  # Add debit account
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
	
	total = 0
	for row in doclist.payment_voucher_kas_pdo:
		total += row.total

	doclist.payment_amount = total
	doclist.grand_total = total
	doclist.outstanding_amount = total

	return doclist

@frappe.whitelist()
def get_available_tipe_pdo(source_name):
	"""Get list of tipe_pdo that still have outstanding amounts"""
	
	doc = frappe.get_doc("Permintaan Dana Operasional", source_name)
	
	available_types = []
	
	tipe_checks = [
		('Bahan Bakar', 'outstanding_amount_bahan_bakar', 'grand_total_bahan_bakar'),
		('Perjalanan Dinas', 'outstanding_amount_perjalanan_dinas', 'grand_total_perjalanan_dinas'),
		('Kas', 'outstanding_amount_kas', 'grand_total_kas'),
		('Dana Cadangan', 'outstanding_amount_dana_cadangan', 'grand_total_dana_cadangan')
	]
	
	for tipe, outstanding_field, grand_total_field in tipe_checks:
		outstanding = getattr(doc, outstanding_field, 0) or 0
		grand_total = getattr(doc, grand_total_field, 0) or 0
		
		# Show option if there's a grand total and outstanding amount > 0
		if grand_total > 0 and outstanding > 0:
			available_types.append({
				'value': tipe,
				'label': f'{tipe} (Outstanding: {frappe.format_value(outstanding, {"fieldtype": "Currency"})})'
			})
	
	return available_types