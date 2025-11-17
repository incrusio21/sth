import frappe
from frappe.utils import flt

from erpnext.accounts.doctype.payment_entry.payment_entry import get_reference_details

from hrms.overrides.employee_payment_entry import (
	EmployeePaymentEntry, 
	get_reference_details_for_employee
)

from sth.controllers.accounts_controller import update_voucher_outstanding
from sth.hr_customize import get_payment_settings

class PaymentEntry(EmployeePaymentEntry):
	def get_valid_reference_doctypes(self):
		
		doc_ref = []
		for d in get_payment_settings("reference"):
			if d.party_type != self.party_type:
				continue
			
			doc_ref.extend(d.doctype_ref.split("\n"))

		return doc_ref
		
	def update_outstanding_amounts(self):
		custom_doctype = get_payment_settings("outstanding_doctype")

		for d in self.get("references"):
			# check field pada payment settings
			if custom_doctype and d.reference_doctype in custom_doctype.split("\n"):
				update_voucher_outstanding(
					d.reference_doctype,
					d.reference_name,
					self.party_account,
					self.party_type,
					self.party,
				)
		
		super().update_outstanding_amounts()

	def set_missing_ref_details(
		self,
		force: bool = False,
		update_ref_details_only_for: list | None = None,
		reference_exchange_details: dict | None = None,
	) -> None:
		for d in self.get("references"):
			if not d.allocated_amount:
				continue
			
			if update_ref_details_only_for and (
				(d.reference_doctype, d.reference_name) not in update_ref_details_only_for
			):
				continue
			
			ref_details = get_payment_reference_details(
				d.reference_doctype,
				d.reference_name,
				self.party_account_currency,
				self.party_type,
				self.party,
			)

			# Only update exchange rate when the reference is Journal Entry
			if (
				reference_exchange_details
				and d.reference_doctype == reference_exchange_details.reference_doctype
				and d.reference_name == reference_exchange_details.reference_name
			):
				ref_details.update({"exchange_rate": reference_exchange_details.exchange_rate})

			for field, value in ref_details.items():
				if d.exchange_gain_loss:
					# for cases where gain/loss is booked into invoice
					# exchange_gain_loss is calculated from invoice & populated
					# and row.exchange_rate is already set to payment entry's exchange rate
					# refer -> `update_reference_in_payment_entry()` in utils.py
					continue

				if field == "exchange_rate" or not d.get(field) or force:
					if self.get("_action") in ("submit", "cancel"):
						d.db_set(field, value)
					else:
						d.set(field, value)
						
@frappe.whitelist()
def get_payment_reference_details(
	reference_doctype, reference_name, party_account_currency, party_type=None, party=None
):
	# check field pada payment settings
	custom_doctype = get_payment_settings("outstanding_doctype")
	if custom_doctype and reference_doctype in custom_doctype.split("\n"):
		return get_reference_details_by_payment_settings(reference_doctype, reference_name, party_account_currency)
	
	if reference_doctype in ("Expense Claim", "Employee Advance", "Gratuity", "Leave Encashment"):
		return get_reference_details_for_employee(reference_doctype, reference_name, party_account_currency)
	else:
		return get_reference_details(
			reference_doctype, reference_name, party_account_currency, party_type, party
		)

@frappe.whitelist()
def get_reference_details_by_payment_settings(reference_doctype, reference_name, party_account_currency):
	"""
	Returns payment reference details for employee related doctypes:
	Employee Advance, Expense Claim, Gratuity, Leave Encashment
	"""
	total_amount = outstanding_amount = exchange_rate = None

	ref_doc = frappe.get_doc(reference_doctype, reference_name)
	# company_currency = ref_doc.get("company_currency") or erpnext.get_company_currency(ref_doc.company)

	total_amount, exchange_rate = ref_doc.grand_total, 1

	outstanding_amount = ref_doc.get("outstanding_amount")

	return frappe._dict(
		{
			"due_date": ref_doc.get("due_date"),
			"total_amount": flt(total_amount),
			"outstanding_amount": flt(outstanding_amount),
			"exchange_rate": flt(exchange_rate),
		}
	)