# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from sth.finance_sth.doctype.disbursement_loan.disbursement_loan import make_disbursement_loan

class LoanBank(Document):
	def on_update(self):
		self.process_disbursement()
		self.process_installment()

	def after_insert(self):
		self.process_disbursement()
		self.process_installment()

	def on_submit(self):
		if not self.disbursements and not self.installments:
			frappe.throw(f"Tabel pencairan dan Angsuran tidak boleh kosong")

		self.process_child_submit()
	
	def before_cancel(self):
		self.process_child_cancel()

	def on_update_after_submit(self):
		if not self.disbursements and not self.installments:
			frappe.throw(f"Tabel pencairan dan Angsuran tidak boleh kosong")
		self.process_disbursement(submit=True)
		self.process_installment(submit=True)

	def process_disbursement(self, submit=False):
		for row in self.disbursements:
			create_disbursement(self, row, submit)
			update_disbursement(self, row)
		
		cond = {
			"reference_doc": "Loan Bank",
			"reference_name": self.name,
		}
		disbursements = frappe.db.get_all("Disbursement Loan", filters=cond, fields="*")
		for d in disbursements:
			delete_disbursement(d)
	
	def process_installment(self, submit=False):
		for row in self.installments:
			create_installment(self, row, submit)
			update_installment(self, row)
		cond = {
			"reference_doc": "Loan Bank",
			"reference_name": self.name,
		}
		installments = frappe.db.get_all("Installment Loan", filters=cond, fields="*")
		for d in installments:
			delete_installment(d)

	def process_child_submit(self):
		for row in self.disbursements:
			doc = frappe.get_doc("Disbursement Loan", row.disbursement_number)
			doc.submit()

		for row in self.disbursements:
			doc = frappe.get_doc("Installment Loan", row.disbursement_number)
			doc.submit()

	def process_child_cancel(self):
		for row in self.disbursements:
			doc = frappe.get_doc("Disbursement Loan", row.disbursement_number)
			doc.cancel()

		for row in self.disbursements:
			doc = frappe.get_doc("Installment Loan", row.disbursement_number)
			doc.cancel()

def create_disbursement(parent, loan_bank, submit=False):
	if not frappe.db.exists("Disbursement Loan", loan_bank.disbursement_number):
		values = {
			"doctype": "Disbursement Loan",
			"disbursement_number": loan_bank.disbursement_number,
			"disbursement_date": loan_bank.disbursement_date,
			"disbursement_amount": loan_bank.disbursement_amount,
			"disbursement_total": loan_bank.disbursement_total,
			"due_days": loan_bank.due_days,
			"reference_doc": "Loan Bank",
			"reference_name": loan_bank.parent,
			"reference_doc_detail": loan_bank.doctype,
			"reference_name_detail": loan_bank.name,
			"company": parent.company,
			"unit": parent.unit,
			"posting_date": loan_bank.disbursement_date,
			"expense_account": parent.expense_account,
			"debit_to": parent.disbursement_debit_to,
			"cost_center": parent.cost_center,
			"grand_total": loan_bank.disbursement_total,
			"outstanding_amount": loan_bank.disbursement_total,
		}
		disbursement_loan = frappe.get_doc(values)
		disbursement_loan.insert(
			ignore_permissions=True
		)
		if submit:
			disbursement_loan.submit()


def update_disbursement(parent, loan_bank):
	doc_type = "Disbursement Loan"
	if frappe.db.exists(doc_type, loan_bank.disbursement_number):
		doc = frappe.get_doc(doc_type, loan_bank.disbursement_number)
		check_fields = [
			"disbursement_date",
			"disbursement_amount",
			"disbursement_total",
			"due_days",
		]

		if is_doc_changed(doc, loan_bank, check_fields):
			doc.disbursement_date = loan_bank.disbursement_date
			doc.disbursement_amount = loan_bank.disbursement_amount
			doc.disbursement_total = loan_bank.disbursement_total
			doc.due_days = loan_bank.due_days
			doc.company = parent.company
			doc.unit = parent.unit
			doc.posting_date = loan_bank.disbursement_date
			doc.expense_account = parent.expense_account
			doc.debit_to = parent.disbursement_debit_to
			doc.cost_center = parent.cost_center
			doc.grand_total = loan_bank.disbursement_total
			doc.outstanding_amount = loan_bank.disbursement_total
			doc.db_update_all()

def is_doc_changed(old_doc, new_doc, fields):
	for field in fields:
		if old_doc.get(field) != new_doc.get(field):
			return True
	return False

def delete_disbursement(disbursements):
	cond = {
		"disbursement_number": disbursements.disbursement_number,
		"name": disbursements.reference_name_detail,
	}
	if not frappe.db.exists(disbursements.reference_doc_detail, cond):
		frappe.db.delete("Disbursement Loan", disbursements.disbursement_number)
		delete_ledger("Disbursement Loan", disbursements.disbursement_number)

def create_installment(parent, loan_bank, submit=False):
	if not frappe.db.exists("Installment Loan", loan_bank.disbursement_number):
		values = {
			"doctype": "Installment Loan",
			"disbursement_number": loan_bank.disbursement_number,
			"disbursement_amount": loan_bank.disbursement_amount,
			"disbursement_date": loan_bank.disbursement_date,
			"disbursement_total": loan_bank.disbursement_total,
			"payment_date": loan_bank.payment_date,
			"installment_month": loan_bank.installment_month,
			"principal": loan_bank.principal,
			"loan_interest": loan_bank.loan_interest,
			"days": loan_bank.days,
			"interest_amount": loan_bank.interest_amount,
			"payment_total": loan_bank.payment_total,
			"reference_doc": "Loan Bank",
			"reference_name": loan_bank.parent,
			"reference_doc_detail": loan_bank.doctype,
			"reference_name_detail": loan_bank.name,
			"company": parent.company,
			"unit": parent.unit,
			"posting_date": loan_bank.payment_date,
			"credit_to": parent.installment_credit_to,
			"debit_to": parent.installment_debit_to,
			"cost_center": parent.cost_center,
			"grand_total": loan_bank.payment_total,
			"outstanding_amount": loan_bank.payment_total,
		}
		installment_loan = frappe.get_doc(values)
		installment_loan.insert(
			ignore_permissions=True
		)
		if submit:
			installment_loan.submit()


def update_installment(parent, loan_bank):
	doc_type = "Installment Loan"
	if frappe.db.exists(doc_type, loan_bank.disbursement_number):
		doc = frappe.get_doc(doc_type, loan_bank.disbursement_number)
		check_fields = [
			"payment_date",
			"installment_month",
			"principal",
			"days",
			"loan_interest",
			"interest_amount",
			"payment_total",
			"disbursement_amount",
			"disbursement_date",
			"disbursement_total",
		]

		if is_doc_changed(doc, loan_bank, check_fields):
			doc.payment_date = loan_bank.payment_date
			doc.installment_month = loan_bank.installment_month
			doc.principal = loan_bank.principal
			doc.days = loan_bank.days
			doc.loan_interest = loan_bank.loan_interest
			doc.interest_amount = loan_bank.interest_amount
			doc.payment_total = loan_bank.payment_total
			doc.disbursement_amount = loan_bank.disbursement_amount
			doc.disbursement_date = loan_bank.disbursement_date
			doc.disbursement_total = loan_bank.disbursement_total
			doc.company = parent.company
			doc.unit = parent.unit
			doc.posting_date = loan_bank.payment_date
			doc.credit_to = parent.installment_credit_to
			doc.debit_to = parent.installment_debit_to
			doc.cost_center = parent.cost_center
			doc.grand_total = loan_bank.payment_total
			doc.outstanding_amount = loan_bank.payment_total
			doc.db_update_all()

def delete_installment(installments):
	cond = {
		"disbursement_number": installments.disbursement_number,
		"name": installments.reference_name_detail,
	}
	if not frappe.db.exists(installments.reference_doc_detail, cond):
		frappe.db.delete("Installment Loan", installments.disbursement_number)
		delete_ledger("Installment Loan", installments.disbursement_number)


def delete_ledger(doc_type, doc_name):
    frappe.db.delete("GL Entry", {"voucher_type": doc_type, "voucher_no": doc_name})


@frappe.whitelist()
def get_last_interest(loan_bank, date):
	interest = frappe.db.get_value("Loan Bank Interest", filters={"loan_bank": loan_bank, "date": ["<=", date]}, fieldname="interest", order_by="date desc")
	if not interest:
		interest = frappe.db.get_value("Loan Bank Interest", filters={"loan_bank": loan_bank}, fieldname="interest", order_by="date desc")
		
	
	return interest

@frappe.whitelist()
def update_loan_bank_interest(doc):
	doc = frappe.parse_json(doc)
	docu = frappe.get_doc(doc.get('doctype'), doc.get('name'))
	docu.date = doc.get("date")
	docu.interest = doc.get("interest")
	docu.save()
	
	return docu

def update_loan_bank_payment_entry(pe, method):
	for ref in pe.references:
		if ref.reference_doctype not in ["Disbursement Loan", "Installment Loan"]:
			continue
		doc = frappe.get_doc(ref.reference_doctype, ref.reference_name)
		doc.payment_entry = pe.name if method == "on_submit" else None
		doc.db_update_all()

		frappe.db.set_value(doc.reference_doc_detail, doc.reference_name_detail, "payment_entry", doc.payment_entry)