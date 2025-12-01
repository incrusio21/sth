# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

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
		self.validate_child_tables()
		
	def on_update(self):
		self.process_data_to_insert_vtwo()

	def on_submit(self):
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
				"debit_to": self.get(f"{fieldname}_debit_to"),
				"credit_to": self.get(f"{fieldname}_credit_to"),
				"reference_doc": "Permintaan Dana Operasional",
				"reference_name": self.name,
				"employee": frappe.db.get_single_value("Payment Settings", "internal_employee"),
				"cost_center": self.get(f"{fieldname}_cost_center"),
				"company": self.company,
				"posting_date": self.posting_date,
				"required_by": self.required_by,
			}
			
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