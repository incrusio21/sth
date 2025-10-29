import frappe
import erpnext
from frappe.utils import cint, comma_or, flt, getdate, nowdate
from erpnext.accounts.doctype.payment_entry.payment_entry import PaymentEntry, get_outstanding_reference_documents
from frappe import ValidationError, _, qb, scrub, throw

class PaymentEntry(PaymentEntry):
	def get_valid_reference_doctypes(self):
		if self.party_type == "Customer":
			return ("Sales Order", "Sales Invoice", "Journal Entry", "Dunning", "Payment Entry", "Employee Advance")
		elif self.party_type in ["Shareholder", "Employee"]:
			return ("Journal Entry", "Employee Advance")
		elif self.party_type == "Supplier":
			return ("Purchase Order", "Purchase Invoice", "Journal Entry", "Payment Entry", "Training Event", "Travel Request")

	def validate_allocated_amount_with_latest_data(self):
		if not self.references:
			return

		uniq_vouchers = {(x.reference_doctype, x.reference_name) for x in self.references}
		vouchers = [frappe._dict({"voucher_type": x[0], "voucher_no": x[1]}) for x in uniq_vouchers]
		latest_references = get_outstanding_reference_documents(
			{
				"posting_date": self.posting_date,
				"company": self.company,
				"party_type": self.party_type,
				"payment_type": self.payment_type,
				"party": self.party,
				"party_account": self.paid_from if self.payment_type == "Receive" else self.paid_to,
				"get_outstanding_invoices": True,
				"get_orders_to_be_billed": True,
				"vouchers": vouchers,
				"book_advance_payments_in_separate_party_account": self.book_advance_payments_in_separate_party_account,
			},
			validate=True,
		)

		# Group latest_references by (voucher_type, voucher_no)
		latest_lookup = {}
		for d in latest_references:
			d = frappe._dict(d)
			latest_lookup.setdefault((d.voucher_type, d.voucher_no), frappe._dict())[d.payment_term] = d

		for idx, d in enumerate(self.get("references"), start=1):
			latest = latest_lookup.get((d.reference_doctype, d.reference_name)) or frappe._dict()

			# skip validasi jika reference adalah Training Event
			if d.reference_doctype == "Training Event":
				continue

			# If term based allocation is enabled, throw
			if (
				d.payment_term is None or d.payment_term == ""
			) and self.term_based_allocation_enabled_for_reference(d.reference_doctype, d.reference_name):
				frappe.throw(
					_(
						"{0} has Payment Term based allocation enabled. Select a Payment Term for Row #{1} in Payment References section"
					).format(frappe.bold(d.reference_name), frappe.bold(idx))
				)

			# if no payment template is used by invoice and has a custom term(no `payment_term`), then invoice outstanding will be in 'None' key
			latest = latest.get(d.payment_term) or latest.get(None)
			# The reference has already been fully paid
			if not latest:
				frappe.throw(
					_("{0} {1} has already been fully paid.").format(_(d.reference_doctype), d.reference_name)
				)
			# The reference has already been partly paid
			elif (
				latest.outstanding_amount < latest.invoice_amount
				and flt(d.outstanding_amount, d.precision("outstanding_amount"))
				!= flt(latest.outstanding_amount, d.precision("outstanding_amount"))
				and d.payment_term == ""
			):
				frappe.throw(
					_(
						"{0} {1} has already been partly paid. Please use the 'Get Outstanding Invoice' or the 'Get Outstanding Orders' button to get the latest outstanding amounts."
					).format(_(d.reference_doctype), d.reference_name)
				)

			fail_message = _("Row #{0}: Allocated Amount cannot be greater than outstanding amount.")

			if (
				d.payment_term
				and (
					(flt(d.allocated_amount)) > 0
					and latest.payment_term_outstanding
					and (flt(d.allocated_amount) > flt(latest.payment_term_outstanding))
				)
				and self.term_based_allocation_enabled_for_reference(d.reference_doctype, d.reference_name)
			):
				frappe.throw(
					_(
						"Row #{0}: Allocated amount:{1} is greater than outstanding amount:{2} for Payment Term {3}"
					).format(d.idx, d.allocated_amount, latest.payment_term_outstanding, d.payment_term)
				)

			if (flt(d.allocated_amount)) > 0 and flt(d.allocated_amount) > flt(latest.outstanding_amount):
				frappe.throw(fail_message.format(d.idx))

			# Check for negative outstanding invoices as well
			if flt(d.allocated_amount) < 0 and flt(d.allocated_amount) < flt(latest.outstanding_amount):
				frappe.throw(fail_message.format(d.idx))

	def validate_allocated_amount(self):
		if self.payment_type == "Internal Transfer":
			return

		self.validate_allocated_amount_as_per_payment_request()

		if self.party_type in ("Customer", "Supplier"):
			self.validate_allocated_amount_with_latest_data()
			return


		fail_message = _("Row #{0}: Allocated Amount cannot be greater than outstanding amount.")
		for d in self.references:
			if (flt(d.allocated_amount)) > 0 and flt(d.allocated_amount) > flt(d.outstanding_amount):
				frappe.throw(fail_message.format(d.idx))

			# Check for negative outstanding invoices as well
			if flt(d.allocated_amount) < 0 and flt(d.allocated_amount) < flt(d.outstanding_amount):
				frappe.throw(fail_message.format(d.idx))

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

			ref_details = get_reference_details(
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
					d.db_set(field, value)

@frappe.whitelist()
def get_reference_details(
	reference_doctype, reference_name, party_account_currency, party_type=None, party=None
):
	total_amount = outstanding_amount = exchange_rate = account = None

	ref_doc = frappe.get_doc(reference_doctype, reference_name)
	company_currency = ref_doc.get("company_currency") or erpnext.get_company_currency(ref_doc.company)

	# Only applies for Reverse Payment Entries
	account_type = None
	payment_type = None

	if reference_doctype == "Dunning":
		total_amount = outstanding_amount = ref_doc.get("dunning_amount")
		exchange_rate = 1

	elif reference_doctype == "Training Event":
		ref_doc = frappe.get_doc(reference_doctype, reference_name)
		total_amount = flt(ref_doc.custom_grand_total_costing)
		paid_amount = flt(ref_doc.custom_grand_total_costing)
		outstanding_amount = flt(ref_doc.custom_grand_total_costing)
		exchange_rate = 1

	elif reference_doctype == "Employee Advance":
		ref_doc = frappe.get_doc(reference_doctype, reference_name)
		total_amount = flt(ref_doc.advance_amount)
		paid_amount = flt(ref_doc.advance_amount)
		outstanding_amount = flt(ref_doc.advance_amount)
		exchange_rate = 1

	elif reference_doctype == "Journal Entry" and ref_doc.docstatus == 1:
		if ref_doc.multi_currency:
			exchange_rate = get_exchange_rate(party_account_currency, company_currency, ref_doc.posting_date)
		else:
			exchange_rate = 1
			outstanding_amount, total_amount = get_outstanding_on_journal_entry(
				reference_name, party_type, party
			)

	elif reference_doctype == "Payment Entry":
		if reverse_payment_details := frappe.db.get_all(
			"Payment Entry",
			filters={"name": reference_name},
			fields=["payment_type", "party_type"],
		)[0]:
			payment_type = reverse_payment_details.payment_type
			account_type = frappe.db.get_value(
				"Party Type", reverse_payment_details.party_type, "account_type"
			)
		exchange_rate = 1

	elif reference_doctype != "Journal Entry":
		if not total_amount:
			if party_account_currency == company_currency:
				# for handling cases that don't have multi-currency (base field)
				total_amount = (
					ref_doc.get("base_rounded_total")
					or ref_doc.get("rounded_total")
					or ref_doc.get("base_grand_total")
					or ref_doc.get("grand_total")
				)
				exchange_rate = 1
			else:
				total_amount = ref_doc.get("rounded_total") or ref_doc.get("grand_total")
		if not exchange_rate:
			# Get the exchange rate from the original ref doc
			# or get it based on the posting date of the ref doc.
			exchange_rate = ref_doc.get("conversion_rate") or get_exchange_rate(
				party_account_currency, company_currency, ref_doc.posting_date
			)

		if reference_doctype in ("Sales Invoice", "Purchase Invoice"):
			outstanding_amount = ref_doc.get("outstanding_amount")
			account = (
				ref_doc.get("debit_to") if reference_doctype == "Sales Invoice" else ref_doc.get("credit_to")
			)
		else:
			outstanding_amount = flt(total_amount) - flt(ref_doc.get("advance_paid"))

		if reference_doctype in ["Sales Order", "Purchase Order"]:
			party_type = "Customer" if reference_doctype == "Sales Order" else "Supplier"
			party_field = "customer" if reference_doctype == "Sales Order" else "supplier"
			party = ref_doc.get(party_field)
			account = get_party_account(party_type, party, ref_doc.company)
	else:
		# Get the exchange rate based on the posting date of the ref doc.
		exchange_rate = get_exchange_rate(party_account_currency, company_currency, ref_doc.posting_date)

	res = frappe._dict(
		{
			"due_date": ref_doc.get("due_date"),
			"total_amount": flt(total_amount),
			"outstanding_amount": flt(outstanding_amount),
			"exchange_rate": flt(exchange_rate),
			"bill_no": ref_doc.get("bill_no"),
			"account_type": account_type,
			"payment_type": payment_type,
		}
	)
	if account:
		res.update({"account": account})
	return res