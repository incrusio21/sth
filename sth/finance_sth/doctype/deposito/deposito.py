# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt
import math
import frappe
import erpnext

from frappe.model.document import Document
from frappe.utils import add_months, date_diff, nowdate, add_days, flt
from frappe.model.mapper import get_mapped_doc
from sth.controllers.accounts_controller import AccountsController
from erpnext.accounts.general_ledger import make_gl_entries

class Deposito(AccountsController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._expense_account = "non_current_asset"

	def validate(self):
		self.calculate_deposito_interest_table()
		self.set_missing_value()

	def on_submit(self):
		if not self.deposito_interest_table:
			frappe.throw("Mohon lakukan perhitungan deposito dengan benar sehingga menghasilkan data di tabel")
		self.make_gl_entry()
		if self.deposito_type in ("Non Roll Over", "Roll Over Pokok"):
			self.make_deposito_interest()


	def on_cancel(self):
		if not self.deposito_interest_table:
			frappe.throw("Mohon lakukan perhitungan deposito dengan benar sehingga menghasilkan data di tabel")
		super().on_cancel()
		self.make_gl_entry()
		self.cancel_deposito_intreset()
		self.cancel_redeemed_deposito()
		

	def calculate_deposito_interest_table(self):
		self.deposito_interest_table = []
		start_date = self.value_date
		end_date = self.value_date

		deposit_amount = self.deposit_amount
		self.interest_amount = 0
		self.tax_amount = 0
		self.total = 0
		for i in range(0, int(self.tenor)):
			end_date = add_months(end_date, 1)
			days = date_diff(end_date, start_date)
			deposit_amount = self.calculate_interest_permonth(start_date, end_date, days, deposit_amount)
			start_date= end_date
	
		self.grand_total_receive = deposit_amount
		self.grand_total = self.deposit_amount
		self.outstanding_amount = self.deposit_amount

	def calculate_interest_permonth(self, value_date, maturity_date, days, deposit_amount):
		interest = self.interest / 100
		tax = self.tax / 100
		year_days = self.year_days
		interest_amount = deposit_amount * interest * days / year_days
		tax_amount = interest_amount * tax
		total = interest_amount - tax_amount

		self.append("deposito_interest_table", {
			"posting_date": self.posting_date,
			"deposito_amount": deposit_amount,
			"interest": self.interest,
			"tax": self.tax,
			"value_date": value_date,
			"maturity_date": maturity_date,
			"day_in_months": days,
			"interest_amount": interest_amount,
			"tax_amount": tax_amount,
			"total": total,
			"grand_total": total,
			"outstanding_amount": total,
			"is_redeemed": "Belum",
			"debit_to": frappe.db.get_value("Company", self.company, "default_deposito_receivable_account"),
			"income_account": frappe.db.get_value("Company", self.company, "default_deposito_income_account")
		})

		self.interest_amount += interest_amount
		self.tax_amount += tax_amount
		self.total += total
		if self.deposito_type == "Roll Over Pokok + Bunga":
			deposit_amount += total
		return deposit_amount

	def make_deposito_interest(self):
		for row in self.deposito_interest_table:
			values = {
				"doctype": "Deposito Interest",
				"company": self.company,
				"unit": self.unit,
				"posting_date": row.posting_date,
				"value_date": row.value_date,
				"maturity_date": row.maturity_date,
				"day_in_months": row.day_in_months,
				"deposito_amount": row.deposito_amount,
				"interest": row.interest,
				"tax": row.tax,
				"interest_amount": row.interest_amount,
				"tax_amount": row.tax_amount,
				"total": row.total,
				"grand_total": row.grand_total,
				"outstanding_amount": row.outstanding_amount,
				"cost_center": row.cost_center,
				"debit_to": row.debit_to,
				"income_account": row.income_account,
				"reference_doc": "Deposito",
				"reference_name": self.name,
				"reference_detail_doc": row.doctype,
				"reference_detail_name": row.name,
			}

			doc = frappe.get_doc(values)
			doc.insert(ignore_permissions=True)
			doc.submit()
			row.deposito_interest = doc.name
			row.db_update_all()

		self.db_update_all()

	def cancel_deposito_intreset(self, is_redeemed=False):
		for row in self.deposito_interest_table:
			doc = frappe.get_doc("Deposito Interest", row.deposito_interest)
			if is_redeemed and not doc.payment_entry and not row.payment:
				doc.cancel()
				row.is_redeemed = "Cancelled"
				row.db_update_all()
			elif not is_redeemed:
				doc.cancel()
		self.db_update_all()


	def cancel_redeemed_deposito(self):
		if self.redeemed_document:
			doc = frappe.get_doc("Redeemed Deposito", self.redeemed_document)
			doc.cancel()

	@frappe.whitelist()
	def make_redemeed_deposito(self):
		company = frappe.db.get_value("Company", self.company, "*")
		grand_total = self.grand_total_receive
		if self.pinalti > 0:
			grand_total = self.grand_total - self.pinalti

		values = {
			"doctype": "Redeemed Deposito",
			"company": self.company,
			"currency": self.currency,
			"posting_date": nowdate(),
			"unit": self.unit,
			"customer": frappe.db.get_single_value('Payment Settings', "receivable_customer"),
			"deposito": self.name,
			"grand_total": flt(grand_total),
			"outstanding_amount": flt(grand_total),
			"cost_center": self.cost_center,
			"debit_to": company.default_deposito_receivable_account,
			"non_current_asset": self.non_current_asset,
		}
		doc = frappe.get_doc(values)
		doc.insert(ignore_permissions=True)
		doc.submit()
		self.redeemed_document = doc.name
		self.is_redeemed = "Sudah"
		self.db_update_all()
		# if self.pinalti == 0 and self.deposito_type == "Roll Over Pokok + Bunga":
		# 	make_roll_over_insterest_gl(self)

	@frappe.whitelist()
	def make_pinalti_deposito(self, pinalti):
		self.pinalti = pinalti
		self.db_update_all()
		self.cancel_deposito_intreset(is_redeemed=True)
		make_pinalti_deposito_ledger(self)
		self.make_redemeed_deposito()


@frappe.whitelist()
def make_payment_entry(source_name, target_doc=None):
	def post_process(source, target):
		receivable_customer = frappe.db.get_single_value("Payment Settings", "receivable_customer")
		customer_name = frappe.db.get_value("Customer", receivable_customer, "customer_name")
		company = frappe.db.get_value("Company", source.company, "*")
		account_currency = frappe.db.get_value("Account", source.debit_to, "account_currency")
		deposito = frappe.get_doc(source.reference_doc, source.reference_name)

		target.payment_type = "Receive"
		target.party_type = "Customer"
		target.party = receivable_customer
		target.party_name = customer_name
		target.paid_amount = source.outstanding_amount
		target.bank_account = deposito.bank_account
		target.paid_from_account_currency = account_currency
		target.paid_to_account_currency = company.default_currency
		target.append("references", {
			"reference_doctype": "Deposito Interest",
			"reference_name": source.name,
			"total_amount": source.grand_total,
			"outstanding_amount": source.outstanding_amount,
			"allocated_amount": source.outstanding_amount
		})
	doclist = get_mapped_doc(
		"Deposito Interest",
		source_name,
		{
			"Deposito Interest": {
				"doctype": "Payment Entry",
				"field_map": {
					"debit_to": "paid_from",
				}
			}
		},
  		target_doc,
		post_process,
	)
 
	return doclist


def update_deposito_payment_entry(pe, method):
	for ref in pe.references:
		if ref.reference_doctype not in ("Deposito Interest", "Deposito", "Redeemed Deposito"):
			continue
		field = {
			"Deposito Interest": "payment_entry",
			"Deposito": "payment_pay",
			"Redeemed Deposito": "payment_entry"
		}
		field_pe = field.get(ref.reference_doctype)
		doc = frappe.get_doc(ref.reference_doctype, ref.reference_name)

		pe_name = pe.name if method == "on_submit" else None
		doc.db_set(field_pe, pe_name) 
		if ref.reference_doctype == "Deposito Interest":
			update_payment_interest(pe, method, doc)
		if ref.reference_doctype == "Redeemed Deposito":
			frappe.db.set_value("Deposito", ref.reference_name, "payment_received", pe_name)
		doc.db_update_all()

def update_is_redeemed(parenttype, parent, childtype):
	child_count = frappe.db.count(childtype, {"parenttype": parenttype, "parent": parent})
	child_pay_count = frappe.db.count(childtype, {"parenttype": parenttype, "parent": parent, "payment": ["!=", None]})
	
	doc = frappe.get_doc(parenttype, parent)
	doc.is_redeemed = "Sudah" if child_count == child_pay_count else "Belum"
	doc.db_update_all()
	

def update_payment_interest(pe, method, doc):
	doc.total_realization = pe.paid_amount if method == "on_submit" else 0
	values = {
			"total_realization" : doc.total_realization,
			"payment" : doc.payment_entry,
			"is_redeemed": "Sudah" if method == "on_submit" else "Belum"
		}
	frappe.db.set_value(doc.reference_detail_doc, doc.reference_detail_name, values)

	total_realization = pe.paid_amount if method == "on_submit" else pe.paid_amount * -1
	deposito = frappe.get_doc("Deposito", doc.reference_name)
	deposito.total_realization = deposito.total_realization + total_realization
	deposito.db_update_all()
	update_is_redeemed(doc.reference_doc, doc.reference_name, doc.reference_detail_doc)

@frappe.whitelist()
def make_principal_payment(source_name, target_doc=None, type=None):
	doctype = "Redeemed Deposito" if type == "Receive" else "Deposito"
	account_type = "debit_to" if type == "Receive" else "credit_to"
	paid_type = "paid_from" if type == "Receive" else "paid_to"
	docname = frappe.db.get_value("Redeemed Deposito", {"deposito": source_name}, "name")
	s_name = docname if type == "Receive" else source_name
	
	def post_process(source, target):
		party_type = "Customer" if type == "Receive" else "Employee"
		payment_type = "Receive" if type == "Receive" else "Pay"
		field_default_party_type = "receivable_customer" if party_type == "Customer" else "internal_employee"
		default_party = frappe.db.get_single_value("Payment Settings", field_default_party_type)
		field_party_name = "customer_name" if party_type == "Customer" else "employee_name"

		party_name = frappe.db.get_value(party_type, default_party, field_party_name)
		company = frappe.db.get_value("Company", source.company, "*")
		account_currency = frappe.db.get_value("Account", source.debit_to, "account_currency")

		target.payment_type = payment_type
		target.party_type = party_type
		target.party = default_party
		target.party_name = party_name
		target.paid_amount = source.outstanding_amount
		target.bank_account = source.bank_account
		target.paid_from_account_currency = account_currency
		target.paid_to_account_currency = company.default_currency
		target.internal_employee = 1 if party_type == "Employee" else 0
		target.append("references", {
			"reference_doctype": doctype,
			"reference_name": source.name,
			"total_amount": source.outstanding_amount,
			"outstanding_amount": source.outstanding_amount,
			"allocated_amount": source.outstanding_amount
		})

	doclist = get_mapped_doc(
		doctype,
		s_name,
		{
			doctype: {
				"doctype": "Payment Entry",
				"field_map": {
					account_type: paid_type,
				}
			}
		},
  		target_doc,
		post_process,
	)
 
	return doclist

def make_pinalti_deposito_ledger(parent):
	company = frappe.db.get_value("Company", parent.company, "*")
	gl_entries = [
		frappe._dict({
			"posting_date": nowdate(),
			"account": company.default_deposito_expense_account,
			"debit": parent.pinalti,
			"credit": 0,
			"company": parent.company,
			"voucher_type": "Deposito",
			"voucher_no": parent.name,
			"cost_center": erpnext.get_default_cost_center(parent.company) if not parent.cost_center else parent.cost_center
		}),
		frappe._dict({
			"posting_date": nowdate(),
			"account": company.default_deposito_nca_account,
			"debit": 0,
			"credit": parent.pinalti,
			"company": parent.company,
			"voucher_type": "Deposito",
			"voucher_no": parent.name,
			"cost_center": erpnext.get_default_cost_center(parent.company) if not parent.cost_center else parent.cost_center
		})
	]

	make_gl_entries(
		gl_entries,
		cancel=False,
		adv_adj=False
	)


def deposito_roll_over():
	query = """
		SELECT * FROM `tabDeposito`
		WHERE 
			is_redeemed = "Belum" 
			AND deposito_type IN ("Roll Over Pokok", "Roll Over Pokok + Bunga") 
			AND DATE_ADD(maturity_date, INTERVAL aro_days DAY) <= CURDATE()
			AND docstatus = 1 AND outstanding_amount = 0
	"""
	
	result = frappe.db.sql(query, as_dict=True)
	if not result:
		return
	
	for row in result:
		print(row.name)
		make_new_depo_roll_over(row)
		old_deposito = frappe.get_doc("Deposito", row.name)
		old_deposito.is_redeemed = "Roll Overed"
		old_deposito.db_update_all()
		
def make_new_depo_roll_over(data):
	make_roll_over_gl(data)
	maturity_aro_date = add_days(data.maturity_date, int(data.aro_days))
	new_maturity_date = add_months(maturity_aro_date, int(data.tenor))
	new_deposito = frappe.new_doc("Deposito")
	new_deposito.company = data.company
	new_deposito.unit = data.unit
	new_deposito.bank = data.bank
	new_deposito.bank_account = data.bank_account
	new_deposito.currency = data.currency
	new_deposito.value_date = maturity_aro_date
	new_deposito.maturity_date = new_maturity_date
	new_deposito.tenor = data.tenor
	new_deposito.interest = data.interest
	new_deposito.tax = data.tax
	new_deposito.bilyet_number = data.bilyet_number
	new_deposito.deposit_amount = data.grand_total_receive
	new_deposito.deposito_type = data.deposito_type
	new_deposito.collateral_owner_name = data.collateral_owner_name
	new_deposito.posting_date = data.posting_date
	new_deposito.deposited_by = data.deposited_by
	new_deposito.aro_days = data.aro_days
	new_deposito.credit_to = data.credit_to
	new_deposito.non_current_asset = data.non_current_asset
	new_deposito.roll_overed_from = data.name
	new_deposito.save()
	new_deposito.submit()

def make_roll_over_gl(data):
	company = frappe.db.get_value("Company", data.company, "*")
	gl_entries = [
		frappe._dict({
			"posting_date": nowdate(),
			"account": company.default_deposito_nca_account,
			"debit": data.grand_total_receive,
			"credit": 0,
			"company": data.company,
			"voucher_type": "Deposito",
			"voucher_no": data.name,
			"cost_center": erpnext.get_default_cost_center(data.company) if not data.cost_center else data.cost_center
		}),
		frappe._dict({
			"posting_date": nowdate(),
			"account": company.default_deposito_receivable_account,
			"debit": 0,
			"credit": data.grand_total_receive,
			"company": data.company,
			"voucher_type": "Deposito",
			"voucher_no": data.name,
			"party_type": "Customer",
			"party": frappe.db.get_single_value("Payment Settings", "receivable_customer"),
			"cost_center": erpnext.get_default_cost_center(data.company) if not data.cost_center else data.cost_center
		})
	]

	make_gl_entries(
		gl_entries,
		cancel=False,
		adv_adj=False
	)
	# frappe.db.commit()


def make_roll_over_insterest_gl(data):
	company = frappe.db.get_value("Company", data.company, "*")
	gl_entries = [
		frappe._dict({
			"posting_date": nowdate(),
			"account": company.default_deposito_receivable_account,
			"debit": data.total,
			"credit": 0,
			"company": data.company,
			"voucher_type": "Redeemed Deposito",
			"voucher_no": data.redeemed_document,
			"party_type": "Customer",
			"party": frappe.db.get_single_value("Payment Settings", "receivable_customer"),
			"cost_center": erpnext.get_default_cost_center(data.company) if not data.cost_center else data.cost_center,
			"againts": data.non_current_asset,
			"against_voucher_type": "Redeemed Deposito",
			"against_voucher": data.redeemed_document,
		}),
		frappe._dict({
			"posting_date": nowdate(),
			"account": data.non_current_asset,
			"debit": 0,
			"credit": data.total,
			"company": data.company,
			"voucher_type": "Redeemed Deposito",
			"voucher_no": data.redeemed_document,
			"cost_center": erpnext.get_default_cost_center(data.company) if not data.cost_center else data.cost_center,
		})
	]

	make_gl_entries(
		gl_entries,
		cancel=False,
		adv_adj=False
	)
	
	values = {
		"outstanding_amount": data.grand_total_receive,
		"grand_total": data.grand_total_receive
	}
	frappe.db.set_value("Redeemed Deposito", data.redeemed_document, values)