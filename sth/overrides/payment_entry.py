import frappe
from frappe import _, scrub
from frappe.model.meta import get_field_precision
from frappe.utils import comma_or, flt, fmt_money, getdate, nowdate

from erpnext.accounts.doctype.payment_entry.payment_entry import get_reference_details, add_regional_gl_entries
from erpnext.accounts.doctype.invoice_discounting.invoice_discounting import (
	get_party_account_based_on_invoice_discounting,
)
from hrms.overrides.employee_payment_entry import (
	EmployeePaymentEntry, 
	get_reference_details_for_employee
)

from sth.controllers.accounts_controller import update_voucher_outstanding
from sth.hr_customize import get_payment_settings

from erpnext.accounts.utils import (
	cancel_exchange_gain_loss_journal,
	get_account_currency,
	get_balance_on,
	get_outstanding_invoices,
)

from erpnext.accounts.general_ledger import (
	make_gl_entries,
	make_reverse_gl_entries,
	process_gl_map,
)

class PaymentEntry(EmployeePaymentEntry):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from erpnext.accounts.doctype.advance_taxes_and_charges.advance_taxes_and_charges import AdvanceTaxesandCharges
		from erpnext.accounts.doctype.payment_entry_deduction.payment_entry_deduction import PaymentEntryDeduction
		from erpnext.accounts.doctype.payment_entry_reference.payment_entry_reference import PaymentEntryReference
		from frappe.types import DF

		amended_from: DF.Link | None
		apply_tax_withholding_amount: DF.Check
		auto_repeat: DF.Link | None
		bank: DF.ReadOnly | None
		bank_account: DF.Link | None
		bank_account_no: DF.ReadOnly | None
		base_in_words: DF.SmallText | None
		base_paid_amount: DF.Currency
		base_paid_amount_after_tax: DF.Currency
		base_received_amount: DF.Currency
		base_received_amount_after_tax: DF.Currency
		base_total_allocated_amount: DF.Currency
		base_total_taxes_and_charges: DF.Currency
		book_advance_payments_in_separate_party_account: DF.Check
		clearance_date: DF.Date | None
		company: DF.Link
		contact_email: DF.Data | None
		contact_person: DF.Link | None
		cost_center: DF.Link | None
		custom_remarks: DF.Check
		deductions: DF.Table[PaymentEntryDeduction]
		difference_amount: DF.Currency
		in_words: DF.SmallText | None
		is_opening: DF.Literal["No", "Yes"]
		letter_head: DF.Link | None
		mode_of_payment: DF.Link | None
		naming_series: DF.Literal["ACC-PAY-.YYYY.-"]
		paid_amount: DF.Currency
		paid_amount_after_tax: DF.Currency
		paid_from: DF.Link
		paid_from_account_balance: DF.Currency
		paid_from_account_currency: DF.Link
		paid_from_account_type: DF.Data | None
		paid_to: DF.Link
		paid_to_account_balance: DF.Currency
		paid_to_account_currency: DF.Link
		paid_to_account_type: DF.Data | None
		party: DF.DynamicLink | None
		party_balance: DF.Currency
		party_bank_account: DF.Link | None
		party_name: DF.Data | None
		party_type: DF.Link | None
		payment_order: DF.Link | None
		payment_order_status: DF.Literal["Initiated", "Payment Ordered"]
		payment_type: DF.Literal["Receive", "Pay", "Internal Transfer"]
		posting_date: DF.Date
		print_heading: DF.Link | None
		project: DF.Link | None
		purchase_taxes_and_charges_template: DF.Link | None
		received_amount: DF.Currency
		received_amount_after_tax: DF.Currency
		reconcile_on_advance_payment_date: DF.Check
		reference_date: DF.Date | None
		reference_no: DF.Data | None
		references: DF.Table[PaymentEntryReference]
		remarks: DF.SmallText | None
		sales_taxes_and_charges_template: DF.Link | None
		source_exchange_rate: DF.Float
		status: DF.Literal["", "Draft", "Submitted", "Cancelled"]
		target_exchange_rate: DF.Float
		tax_withholding_category: DF.Link | None
		taxes: DF.Table[AdvanceTaxesandCharges]
		title: DF.Data | None
		total_allocated_amount: DF.Currency
		total_taxes_and_charges: DF.Currency
		unallocated_amount: DF.Currency
	# end: auto-generated types

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._payment_settings = get_payment_settings()

	def get_valid_reference_doctypes(self):
		
		doc_ref = []
		for d in self._payment_settings.get("reference"):
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
				# if self.unit and self.unit != ref_doc.get("unit"):
				# 	frappe.throw(
				# 		_("{0} {1} is not associated with Unit {2}").format(
				# 			_(d.reference_doctype), d.reference_name, self.unit
				# 		)
				# 	)

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

	def validate_allocated_amount(self):
		if self.payment_type == "Internal Transfer":
			return

		self.validate_allocated_amount_as_per_payment_request()

		if self.party_type in ("Customer", "Supplier"):
			self.validate_allocated_amount_with_latest_data()
			return

		custom_doctype = self._payment_settings.get_outstanding_doctype()
		fail_message = _("Row #{0}: Allocated Amount cannot be greater than outstanding amount.")
		for d in self.get("references"):
			if custom_doctype and d.reference_doctype in custom_doctype \
				and not d.payment_term \
				and frappe.db.exists("Proposal Schedule", {"parent": d.reference_name, "parenttype": d.reference_doctype, "payment_term": ["is", "set"]}):
				frappe.throw(_(f"Row #{d.idx}: Please select a Payment Term"))

			if (flt(d.allocated_amount)) > 0 and flt(d.allocated_amount) > flt(d.outstanding_amount):
				frappe.throw(fail_message.format(d.idx))

			# Check for negative outstanding invoices as well
			if flt(d.allocated_amount) < 0 and flt(d.allocated_amount) < flt(d.outstanding_amount):
				frappe.throw(fail_message.format(d.idx))
		
	def update_payment_schedule(self, cancel=0):
		invoice_payment_amount_map = {}
		invoice_paid_amount_map = {}

		custom_doctype = self._payment_settings.get_outstanding_doctype()
		for ref in self.get("references"):
			if not ref.payment_term or not ref.reference_name:
				continue

			schedule_doctype = "Proposal Schedule" if ref.reference_doctype in custom_doctype else "Payment Schedule"
			key = (ref.payment_term, ref.reference_name, ref.reference_doctype, schedule_doctype)
			invoice_payment_amount_map.setdefault(key, 0.0)
			invoice_payment_amount_map[key] += ref.allocated_amount

			if not invoice_paid_amount_map.get(key):
				payment_schedule = frappe.get_all(
					schedule_doctype,
					filters={"parent": ref.reference_name},
					fields=[
						"paid_amount",
						"payment_amount",
						"payment_term",
						"discount",
						"outstanding",
						"discount_type",
					],
				)
				for term in payment_schedule:
					invoice_key = (term.payment_term, ref.reference_name, ref.reference_doctype, schedule_doctype)
					invoice_paid_amount_map.setdefault(invoice_key, {})
					invoice_paid_amount_map[invoice_key]["outstanding"] = term.outstanding
					if not (term.discount_type and term.discount):
						continue

					if term.discount_type == "Percentage":
						invoice_paid_amount_map[invoice_key]["discounted_amt"] = ref.total_amount * (
							term.discount / 100
						)
					else:
						invoice_paid_amount_map[invoice_key]["discounted_amt"] = term.discount

		for idx, (key, allocated_amount) in enumerate(invoice_payment_amount_map.items(), 1):
			if not invoice_paid_amount_map.get(key):
				frappe.throw(_("Payment term {0} not used in {1}").format(key[0], key[1]))

			allocated_amount = self.get_allocated_amount_in_transaction_currency(
				allocated_amount, key[2], key[1]
			)

			outstanding = flt(invoice_paid_amount_map.get(key, {}).get("outstanding"))
			discounted_amt = flt(invoice_paid_amount_map.get(key, {}).get("discounted_amt"))

			conversion_rate = frappe.db.get_value(key[2], {"name": key[1]}, "conversion_rate")
			base_paid_amount_precision = get_field_precision(
				frappe.get_meta(schedule_doctype).get_field("base_paid_amount")
			)
			base_outstanding_precision = get_field_precision(
				frappe.get_meta(schedule_doctype).get_field("base_outstanding")
			)

			base_paid_amount = flt(
				(allocated_amount - discounted_amt) * conversion_rate, base_paid_amount_precision
			)
			base_outstanding = flt(allocated_amount * conversion_rate, base_outstanding_precision)

			if cancel:
				frappe.db.sql(
					"""
					UPDATE `tab{}`
					SET
						paid_amount = `paid_amount` - %s,
						base_paid_amount = `base_paid_amount` - %s,
						discounted_amount = `discounted_amount` - %s,
						outstanding = `outstanding` + %s,
						base_outstanding = `base_outstanding` - %s
					WHERE parent = %s and payment_term = %s""".format(key[3]),
					(
						allocated_amount - discounted_amt,
						base_paid_amount,
						discounted_amt,
						allocated_amount,
						base_outstanding,
						key[1],
						key[0],
					),
				)
			else:
				if allocated_amount > outstanding:
					frappe.throw(
						_("Row #{0}: Cannot allocate more than {1} against payment term {2}").format(
							idx, fmt_money(outstanding), key[0]
						)
					)

				if allocated_amount and outstanding:
					frappe.db.sql(
						"""
						UPDATE `tab{}`
						SET
							paid_amount = `paid_amount` + %s,
							base_paid_amount = `base_paid_amount` + %s,
							discounted_amount = `discounted_amount` + %s,
							outstanding = `outstanding` - %s,
							base_outstanding = `base_outstanding` - %s
						WHERE parent = %s and payment_term = %s""".format(key[3]),
						(
							allocated_amount - discounted_amt,
							base_paid_amount,
							discounted_amt,
							allocated_amount,
							base_outstanding,
							key[1],
							key[0],
						),
					)
					
	def update_outstanding_amounts(self):
		custom_doctype = self._payment_settings.get_outstanding_doctype()

		for d in self.get("references"):
			# check field pada payment settings
			if custom_doctype and d.reference_doctype in custom_doctype:
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

	def build_gl_map(self):
		if self.payment_type in ("Receive", "Pay") and not self.get("party_account_field"):
			self.setup_party_account_field()
		self.set_transaction_currency_and_rate()

		gl_entries = []
		self.add_party_gl_entries(gl_entries)

		self.add_bank_gl_entries(gl_entries)
		print(gl_entries)

		self.add_deductions_gl_entries(gl_entries)
		self.add_tax_gl_entries(gl_entries)
		add_regional_gl_entries(gl_entries, self)
		return gl_entries

	def make_gl_entries(self, cancel=0, adv_adj=0):
		gl_entries = self.build_gl_map()
		gl_entries = process_gl_map(gl_entries)
		make_gl_entries(gl_entries, cancel=cancel, adv_adj=adv_adj)
		if cancel:
			cancel_exchange_gain_loss_journal(frappe._dict(doctype=self.doctype, name=self.name))
		else:
			self.make_exchange_gain_loss_journal()

		self.make_advance_gl_entries(cancel=cancel)

	def add_bank_gl_entries(self, gl_entries):
		if self.payment_type in ("Pay", "Internal Transfer"):
			gl_entries.append(
				self.get_gl_dict(
					{
						"account": self.paid_from,
						"account_currency": self.paid_from_account_currency,
						"against": self.party if self.payment_type == "Pay" else self.paid_to,
						"credit_in_account_currency": self.paid_amount,
						"credit_in_transaction_currency": self.paid_amount
						if self.paid_from_account_currency == self.transaction_currency
						else self.base_paid_amount / self.transaction_exchange_rate,
						"credit": self.base_paid_amount,
						"cost_center": self.cost_center,
						"post_net_value": True,
					},
					item=self,
				)
			)
		if self.payment_type in ("Receive", "Internal Transfer"):

			if self.payment_type == "Internal Transfer" and not self.tipe_transfer:
				gl_entries.append(
					self.get_gl_dict(
						{
							"account": self.paid_to,
							"account_currency": self.paid_to_account_currency,
							"against": self.party if self.payment_type == "Receive" else self.paid_from,
							"debit_in_account_currency": self.received_amount,
							"debit_in_transaction_currency": self.received_amount
							if self.paid_to_account_currency == self.transaction_currency
							else self.base_received_amount / self.transaction_exchange_rate,
							"debit": self.base_received_amount,
							"cost_center": self.cost_center,
						},
						item=self,
					)
				)

			if self.payment_type == "Internal Transfer" and (self.tipe_transfer == "PDO" or self.tipe_transfer == "Penerimaan Dana PDO"):
				gl_entries.append(
					self.get_gl_dict(
						{
							"account": self.paid_to,
							"account_currency": self.paid_to_account_currency,
							"against": self.party if self.payment_type == "Receive" else self.paid_from,
							"debit_in_account_currency": self.received_amount,
							"debit_in_transaction_currency": self.received_amount
							if self.paid_to_account_currency == self.transaction_currency
							else self.base_received_amount / self.transaction_exchange_rate,
							"debit": self.base_received_amount,
							"cost_center": self.cost_center,
						},
						item=self,
					)
				)
			elif self.tipe_transfer == "Salary Slip":
				# mulai iterasi untuk ambil semua punya salary component
				for baris_ss in self.payment_voucher_salary_slip:
					ss_doc = frappe.get_doc("Salary Slip", baris_ss.salary_slip)
					for ear in ss_doc.earnings:
						com = frappe.get_doc("Salary Component", ear.salary_component)
						if com.not_include_net_pay == 0:
							# baru masuk
							company = self.company
							account = ""
							for acc in com.accounts:
								if acc.company == company:
									account = acc.account

							if not account:
								frappe.throw("Account for Component {} Company {} is not found.".format(ear.salary_component, self.company))
							else:
								gl_entries.append(
									self.get_gl_dict(
										{
											"account": account,
											"account_currency": self.paid_to_account_currency,
											"against": self.party if self.payment_type == "Receive" else self.paid_from,
											"debit_in_account_currency": ear.amount,
											"debit_in_transaction_currency": ear.amount,
											"debit": ear.amount,
											"cost_center": self.cost_center or frappe.get_doc("Company", self.company).cost_center,
										},
										item=self,
									)
								)

					for ear in ss_doc.deductions:
						com = frappe.get_doc("Salary Component", ear.salary_component)
						if com.not_include_net_pay == 0:
							# baru masuk
							company = self.company
							account = ""
							for acc in com.accounts:
								if acc.company == company:
									account = acc.account

							if not account:
								frappe.throw("Account for Component {} Company {} is not found.".format(ear.salary_component, self.company))
							else:
								gl_entries.append(
									self.get_gl_dict(
										{
											"account": account,
											"account_currency": self.paid_to_account_currency,
											"against": self.party if self.payment_type == "Receive" else self.paid_from,
											"credit_in_account_currency": ear.amount,
											"credit_in_transaction_currency": ear.amount,
											"credit": ear.amount,
											"cost_center": self.cost_center or frappe.get_doc("Company", self.company).cost_center,
										},
										item=self,
									)
								)

			elif self.tipe_transfer == "Realisasi PDO":
				for satu_pdo in self.payment_voucher_kas_pdo:
					gl_entries.append(
						self.get_gl_dict(
							{
								"account": satu_pdo.debit_to,
								"account_currency": self.paid_to_account_currency,
								"against": self.party if self.payment_type == "Receive" else self.paid_from,
								"debit_in_account_currency": satu_pdo.total,
								"debit_in_transaction_currency": satu_pdo.total,
								"debit": satu_pdo.total,
								"cost_center": self.cost_center or frappe.get_doc("Company", self.company).cost_center,
							},
							item=self,
						)
					)




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

	if self.payment_voucher_kas_pdo:
		update_outstanding_pdo(self)
		update_tipe_pdo_outstanding(self)
		update_pdo_non_pdo_table(self)
		check_plafon_and_split_excess(self)

def on_cancel_pdo(self,method):
	if self.permintaan_dana_operasional:
		clear_permintaan_dana_operasional(self)

	if self.payment_voucher_kas_pdo:
		update_outstanding_pdo(self)

def update_outstanding_pdo(doc):
	# Collect all unique PDO nos from the Payment Voucher Kas PDO table
	pdo_list = set()
	for row in doc.payment_voucher_kas_pdo:
		if row.no_pdo:
			pdo_list.add(row.no_pdo)
	
	for no_pdo in pdo_list:
		recalculate_pdo_outstanding(no_pdo)

def recalculate_pdo_outstanding(no_pdo):
	# Get the approved amount from PDO
	pdo_amount = frappe.db.get_value(
		"Permintaan Dana Operasional", 
		no_pdo, 
		"grand_total_pdo"  # adjust field name as needed
	)
	
	if not pdo_amount:
		return

	# Sum all submitted Payment Entry amounts linked to this PDO
	# via the Payment Voucher Kas PDO child table
	result = frappe.db.sql("""
		SELECT SUM(pvk.total)
		FROM `tabPayment Entry` pe
		JOIN `tabPayment Voucher Kas PDO` pvk ON pvk.parent = pe.name
		WHERE pvk.no_pdo = %s
		AND pe.docstatus = 1
	""", (no_pdo,), as_dict=False)

	total_realisasi = result[0][0] or 0

	outstanding = pdo_amount - total_realisasi

	frappe.db.set_value(
		"Permintaan Dana Operasional",
		no_pdo,
		"outstanding_amount",
		outstanding
	)

	if outstanding == 0:
		frappe.db.set_value(
			"Permintaan Dana Operasional",
			no_pdo,
			"realisasi_status",
			"Realized"
		)
	else:
		frappe.db.set_value(
			"Permintaan Dana Operasional",
			no_pdo,
			"realisasi_status",
			"Not Realized"
		)

	frappe.db.commit()

def update_permintaan_dana_operasional(self):
	try:
		pdo = frappe.get_doc("Permintaan Dana Operasional", self.permintaan_dana_operasional)
		if self.tipe_transfer == "PDO":
			if pdo.payment_voucher and pdo.payment_voucher != self.name:
				frappe.throw(_(
					"Permintaan Dana Operasional {0} is already linked to Payment Voucher {1}"
				).format(pdo.name, pdo.payment_voucher))
			
			pdo.db_set("payment_voucher", self.name)
			
			frappe.msgprint(_(
				"Permintaan Dana Operasional {0} updated successfully"
			).format(pdo.name))

		elif self.tipe_transfer == "Penerimaan Dana PDO":
			if pdo.payment_voucher_kebun and pdo.payment_voucher_kebun != self.name:
				frappe.throw(_(
					"Permintaan Dana Operasional {0} is already linked to Payment Voucher {1}"
				).format(pdo.name, pdo.payment_voucher_kebun))
			
			pdo.db_set("payment_voucher_kebun", self.name)
			
			frappe.msgprint(_(
				"Permintaan Dana Operasional {0} updated successfully"
			).format(pdo.name))

		elif self.tipe_transfer == "Realisasi PDO":
			already_linked = any(
				row.payment_voucher_kas == self.name
				for row in pdo.get("realisasi_pdo", [])
			)

			if not already_linked:
				pdo.append("realisasi_pdo", {
					"payment_voucher_kas": self.name
				})
				pdo.save(ignore_permissions=True)

				frappe.msgprint(_(
					"Permintaan Dana Operasional {0} updated successfully"
				).format(pdo.name))
			else:
				frappe.msgprint(_(
					"Payment Voucher {0} is already linked in Realisasi PDO of {1}"
				).format(self.name, pdo.name))

		
	except Exception as e:
		frappe.log_error(
			message=frappe.get_traceback(),
			title=f"Error updating PDO {self.permintaan_dana_operasional}"
		)
		frappe.throw(_("Failed to update Permintaan Dana Operasional: {0}").format(str(e)))

	# update if realisasi


def clear_permintaan_dana_operasional(self):
	try:
		pdo = frappe.get_doc("Permintaan Dana Operasional", self.permintaan_dana_operasional)

		if self.tipe_transfer == "Realisasi PDO":
			# Remove only the row linked to this payment voucher
			rows_to_remove = [
				row for row in pdo.get("realisasi_pdo", [])
				if row.payment_voucher_kas == self.name
			]
			for row in rows_to_remove:
				pdo.remove(row)

			if rows_to_remove:
				pdo.save(ignore_permissions=True)
				frappe.msgprint(_(
					"Permintaan Dana Operasional {0} cleared successfully"
				).format(pdo.name))
		else:
			pdo.db_set("payment_voucher", None)
			pdo.db_set("payment_voucher_kebun", None)

			frappe.msgprint(_(
				"Permintaan Dana Operasional {0} cleared successfully"
			).format(pdo.name))

	except Exception as e:
		frappe.log_error(
			message=frappe.get_traceback(),
			title=f"Error clearing PDO {self.permintaan_dana_operasional}"
			)
def debug():
	t = frappe.get_doc("Payment Entry","PDO-00050")
	# t.permintaan_dana_operasional = "PDO-00042"
	# t.db_update()
	# frappe.db.commit()
	on_submit_pdo(t,"on_submit")


def update_tipe_pdo_outstanding(self):
	"""Deduct paid amount from PDO outstanding"""
	if not self.payment_voucher_kas_pdo:
		return
	
	# Group by PDO and tipe
	pdo_payments = {}
	for row in self.payment_voucher_kas_pdo:
		key = (row.no_pdo, row.tipe_pdo)
		if key not in pdo_payments:
			pdo_payments[key] = 0
		pdo_payments[key] += row.total or 0
	
	# Update each PDO
	for (pdo_name, tipe_pdo), total_paid in pdo_payments.items():
		update_outstanding_amount_per_tipe(self, pdo_name, tipe_pdo, total_paid, operation='subtract')

def update_outstanding_amount_per_tipe(self, pdo_name, tipe_pdo, amount, operation='subtract'):
		
	tipe_mapping = {
		'Bahan Bakar': 'outstanding_amount_bahan_bakar',
		'Perjalanan Dinas': 'outstanding_amount_perjalanan_dinas',
		'Kas': 'outstanding_amount_kas',
		'Dana Cadangan': 'outstanding_amount_dana_cadangan'
	}
	
	if tipe_pdo not in tipe_mapping:
		frappe.log_error(f"Unknown tipe_pdo: {tipe_pdo}", "Payment Voucher Kas Outstanding Update")
		return
	
	outstanding_field = tipe_mapping[tipe_pdo]
	
	try:
		pdo = frappe.get_doc("Permintaan Dana Operasional", pdo_name)
		current_outstanding = getattr(pdo, outstanding_field, 0) or 0
		
		if operation == 'subtract':
			new_outstanding = current_outstanding - amount
		else:  # add
			new_outstanding = current_outstanding + amount
		
		# Ensure outstanding doesn't go negative
		new_outstanding = max(0, new_outstanding)
		
		pdo.db_set(outstanding_field, new_outstanding)
		
	except Exception as e:
		frappe.log_error(
			message=frappe.get_traceback(),
			title=f"Error updating PDO {pdo_name} outstanding"
		)
		frappe.throw(_("Failed to update outstanding amount: {0}").format(str(e)))

def update_pdo_non_pdo_table(self):
	"""
	Add rows without pdo_child_name to pdo_non_pdo table
	Loop through each row and add to respective PDO
	"""
	# Group rows by no_pdo
	pdo_groups = {}
	
	for row in self.get('payment_voucher_kas_pdo', []):
		# Skip rows that already have pdo_child_name
		if row.pdo_child_name:
			continue
		
		# Get no_pdo from the row
		no_pdo = row.no_pdo if hasattr(row, 'no_pdo') else None
		
		if not no_pdo:
			continue
		
		if no_pdo not in pdo_groups:
			pdo_groups[no_pdo] = []
		
		pdo_groups[no_pdo].append(row)
	
	# Process each PDO group
	for no_pdo, rows in pdo_groups.items():
		try:
			pdo_doc = frappe.get_doc('Permintaan Dana Operasional', no_pdo)
			
			for row in rows:
				# Get employee details
				jabatan = None
				if row.penerima:
					try:
						employee_doc = frappe.get_doc('Employee', row.penerima)
						jabatan = employee_doc.designation
					except:
						pass
				
				add_to_non_pdo(self,
					pdo_doc=pdo_doc,
					employee=row.penerima,
					jabatan=jabatan,
					debit_to=row.debit_to,
					amount=row.total
				)
			
			# Save the PDO document once after all additions
			pdo_doc.flags.ignore_permissions = True
			pdo_doc.flags.ignore_validate = True
			pdo_doc.save()
			
			frappe.msgprint(
				msg=f'Successfully added {len(rows)} non-PDO entries to {no_pdo}',
				title='PDO Updated',
				indicator='green'
			)
			
		except frappe.DoesNotExistError:
			frappe.msgprint(
				msg=f'Permintaan Dana Operasional {no_pdo} not found',
				title='Error',
				indicator='red'
			)
def add_to_non_pdo(self, pdo_doc, employee, jabatan, debit_to, amount, reason=None):
	"""
	Add entry to pdo_non_pdo table in Permintaan Dana Operasional
	"""
	# Check if similar entry already exists
	existing = False
	for pdo_row in pdo_doc.get('pdo_non_pdo', []):
		if (pdo_row.employee == employee and 
			pdo_row.debit_to == debit_to and 
			abs(flt(pdo_row.total) - flt(amount)) < 0.01):  # Allow small rounding differences
			existing = True
			break
	
	if not existing:
		new_row = pdo_doc.append('pdo_non_pdo', {
			'employee': employee,
			'jabatan': jabatan,
			'debit_to': debit_to,
			'price': amount,
			'qty': 1,
			'total': amount,

			'revised_qty': 1,
			'revised_price': amount,
			'revised_total': amount

		})
		
		# Add remark if field exists
		if reason and hasattr(new_row, 'remarks'):
			new_row.remarks = reason
		elif reason and hasattr(new_row, 'remark'):
			new_row.remark = reason	

def check_plafon_and_split_excess(self):
	current_date = getdate(self.posting_date if hasattr(self, 'posting_date') else nowdate())
	current_month = current_date.month
	current_year = current_date.year
	unit = self.unit if hasattr(self, 'unit') else None
	pdo_groups = {}

	for row in self.get('payment_voucher_kas_pdo', []):
		no_pdo = row.no_pdo if hasattr(row, 'no_pdo') else None
		
		if not no_pdo:
			continue
		
		if not row.penerima:
			continue
		
		try:
			employee_doc = frappe.get_doc('Employee', row.penerima)
			designation = employee_doc.designation
		except:
			continue
		
		if not designation:
			continue
		
		plafon_info = self.get_plafon_for_designation(designation)
		
		print(plafon_info)
		if not plafon_info:
			continue
		
		plafon_amount = flt(plafon_info.get('nilai', 0))
		
		if plafon_amount <= 0:
			continue
		
		total_used = self.calculate_total_usage(
			designation=designation,
			unit=unit,
			month=current_month,
			year=current_year,
			exclude_realisasi=self.name
		)
		


		current_amount = flt(row.total)
		new_total = total_used + current_amount
		
		if new_total > plafon_amount:
			excess_amount = new_total - plafon_amount
			allowed_amount = current_amount - excess_amount
			
			if allowed_amount < 0:
				allowed_amount = 0
				excess_amount = current_amount
			
			if allowed_amount > 0:
				row.total = allowed_amount
				if hasattr(row, 'amount'):
					row.amount = allowed_amount
			else:
				row.total = 0
				if hasattr(row, 'amount'):
					row.amount = 0
			
			if no_pdo not in pdo_groups:
				pdo_groups[no_pdo] = []
			
			pdo_groups[no_pdo].append({
				'employee': row.penerima,
				'jabatan': designation,
				'debit_to': row.debit_to,
				'amount': excess_amount,
			})

			frappe.msgprint(
				msg=f'Employee {row.penerima} ({designation}) exceeded plafon by {excess_amount}. '
					f'Moved to Non-PDO table in {no_pdo}.',
				title='Plafon Exceeded',
				indicator='orange'
			)

	for no_pdo, excess_items in pdo_groups.items():
		try:
			pdo_doc = frappe.get_doc('Permintaan Dana Operasional', no_pdo)
			
			for item in excess_items:
				self.add_to_non_pdo(
					pdo_doc=pdo_doc,
					employee=item['employee'],
					jabatan=item['jabatan'],
					debit_to=item['debit_to'],
					amount=item['amount']
				)
			
			# Save the PDO document once after all additions
			pdo_doc.flags.ignore_permissions = True
			pdo_doc.flags.ignore_validate = True
			pdo_doc.save()
			
		except frappe.DoesNotExistError:
			frappe.msgprint(
				msg=f'Permintaan Dana Operasional {no_pdo} not found',
				title='Error',
				indicator='red'
			)

def get_plafon_for_designation(self, designation):
	try:
		plafon_pdo = frappe.get_doc('Plafon PDO', 'UANG PEMBANTU')
	except:
		return None
	
	for plafon_row in plafon_pdo.get('plafon_pdo_table', []):
		
		if plafon_row.jenis_plafon == designation and plafon_row.tipe == "Designation":
			return {
				'nilai': plafon_row.nilai,
				'jenis_plafon': plafon_row.get('jenis_plafon'),
			}
	
	return None

def calculate_total_usage(self, designation, unit, month, year, exclude_realisasi=None):
	"""
	Calculate total usage for a designation in a specific unit and month
	"""
	# Build filters
	filters = {
		'docstatus': ['in', [0, 1]],  # Draft and Submitted
		'tipe_transfer': ['in', ["Realisasi PDO"]]
	}
	
	if exclude_realisasi:
		filters['name'] = ['!=', exclude_realisasi]
	
	# Get all Realisasi PDO for the month
	realisasi_list = frappe.get_all(
		'Payment Entry',
		filters=filters,
		fields=['name', 'posting_date', 'unit'] if hasattr(self, 'unit') else ['name', 'posting_date']
	)
	
	total = 0
	
	for realisasi in realisasi_list:
		# Check if same month and year
		r_date = getdate(realisasi.posting_date)
		if r_date.month != month or r_date.year != year:
			continue
		
		# Check if same unit (if unit filtering is needed)
		if unit and hasattr(realisasi, 'unit') and realisasi.unit != unit:
			continue
		
		# Get child table entries
		child_entries = frappe.get_all(
			'Payment Voucher Kas PDO',  # Child table doctype name
			filters={
				'parent': realisasi.name,
				'parenttype': 'Realisasi PDO'
			},
			fields=['penerima', 'total']
		)
		
		for entry in child_entries:
			if not entry.penerima:
				continue
			
			# Get employee designation
			try:
				emp = frappe.get_doc('Employee', entry.penerima)
				if emp.designation == designation:
					total += flt(entry.total)
			except:
				continue
	
	return total