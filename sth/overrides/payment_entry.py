import frappe
from frappe import _, scrub
from frappe.utils import comma_or, flt

from erpnext.accounts.doctype.payment_entry.payment_entry import get_reference_details
from erpnext.accounts.doctype.invoice_discounting.invoice_discounting import (
	get_party_account_based_on_invoice_discounting,
)
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
	
	def validate_reference_documents(self):
		valid_reference_doctypes = self.get_valid_reference_doctypes()

		if not valid_reference_doctypes:
			return

		for d in self.get("references"):
			if not d.allocated_amount:
				continue

			if d.reference_doctype not in valid_reference_doctypes:
				frappe.throw(
					_("Reference Doctype must be one of {0}").format(
						comma_or([_(d) for d in valid_reference_doctypes])
					)
				)

			elif d.reference_name:
				if not frappe.db.exists(d.reference_doctype, d.reference_name):
					frappe.throw(_("{0} {1} does not exist").format(d.reference_doctype, d.reference_name))

				ref_doc = frappe.get_doc(d.reference_doctype, d.reference_name)
				
				# memastika pembayaran sesuai dengan unit yang di pilih
				if self.unit and self.unit != ref_doc.get("unit"):
					frappe.throw(
						_("{0} {1} is not associated with Unit {2}").format(
							_(d.reference_doctype), d.reference_name, self.unit
						)
					)

				if d.reference_doctype != "Journal Entry":
					if self.party != ref_doc.get(scrub(self.party_type)):
						frappe.throw(
							_("{0} {1} is not associated with {2} {3}").format(
								_(d.reference_doctype), d.reference_name, _(self.party_type), self.party
							)
						)
				else:
					self.validate_journal_entry()

				if d.reference_doctype in frappe.get_hooks("invoice_doctypes"):
					if self.party_type == "Customer":
						ref_party_account = (
							get_party_account_based_on_invoice_discounting(d.reference_name)
							or ref_doc.debit_to
						)
					elif self.party_type == "Supplier":
						ref_party_account = ref_doc.credit_to
					elif self.party_type == "Employee":
						ref_party_account = ref_doc.payable_account

					if (
						ref_party_account != self.party_account
						and not self.book_advance_payments_in_separate_party_account
					):
						frappe.throw(
							_("{0} {1} is associated with {2}, but Party Account is {3}").format(
								_(d.reference_doctype),
								d.reference_name,
								ref_party_account,
								self.party_account,
							)
						)

					if ref_doc.doctype == "Purchase Invoice" and ref_doc.get("on_hold"):
						frappe.throw(
							_("{0} {1} is on hold").format(_(d.reference_doctype), d.reference_name),
							title=_("Invalid Purchase Invoice"),
						)

				if ref_doc.docstatus != 1:
					frappe.throw(
						_("{0} {1} must be submitted").format(_(d.reference_doctype), d.reference_name)
					)

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

	def validate_transaction_reference(self):
		bank_account = self.paid_to if self.payment_type == "Receive" else self.paid_from
		bank_account_type = frappe.get_cached_value("Account", bank_account, "account_type")

		# if bank_account_type == "Bank":
		# 	if not self.reference_no or not self.reference_date:
		# 		frappe.throw(_("Reference No and Reference Date is mandatory for Bank transaction"))
						
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

def on_submit_pdo(self,method):
	if self.permintaan_dana_operasional:
		update_permintaan_dana_operasional(self)

def on_cancel_pdo(self,method):
	if self.permintaan_dana_operasional:
		clear_permintaan_dana_operasional(self)

def update_permintaan_dana_operasional(self):
	try:
		pdo = frappe.get_doc("Permintaan Dana Operasional", self.permintaan_dana_operasional)
		
		if pdo.payment_voucher and pdo.payment_voucher != self.name:
			frappe.throw(_(
				"Permintaan Dana Operasional {0} is already linked to Payment Voucher {1}"
			).format(pdo.name, pdo.payment_voucher))
		
		pdo.db_set("payment_voucher", self.name)
		
		frappe.msgprint(_(
			"Permintaan Dana Operasional {0} updated successfully"
		).format(pdo.name))
		
	except Exception as e:
		frappe.log_error(
			message=frappe.get_traceback(),
			title=f"Error updating PDO {self.permintaan_dana_operasional}"
		)
		frappe.throw(_("Failed to update Permintaan Dana Operasional: {0}").format(str(e)))

def clear_permintaan_dana_operasional(self):
	try:
		pdo = frappe.get_doc("Permintaan Dana Operasional", self.permintaan_dana_operasional)
		pdo.db_set("payment_voucher", None)
		
		frappe.msgprint(_(
			"Permintaan Dana Operasional {0} cleared successfully"
		).format(pdo.name))
		
	except Exception as e:
		frappe.log_error(
			message=frappe.get_traceback(),
			title=f"Error clearing PDO {self.permintaan_dana_operasional}"
		)