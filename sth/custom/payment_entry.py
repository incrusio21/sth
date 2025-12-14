import frappe
import json

from frappe import _, qb
from frappe.utils import getdate, nowdate
from erpnext.accounts.doctype.payment_entry.payment_entry import get_orders_to_be_billed, split_invoices_based_on_payment_terms, get_negative_outstanding_invoices
from erpnext.controllers.accounts_controller import get_supplier_block_status
from erpnext.accounts.utils import get_account_currency, get_outstanding_invoices
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import get_dimensions
from erpnext.accounts.party import get_party_account
from erpnext.setup.utils import get_exchange_rate

from sth.finance_sth.doctype.cheque_number.cheque_number import update_cheque_number_pe
from sth.finance_sth.doctype.cheque_book.cheque_book import update_cheque_book_pe, delete_cheque_history
from sth.finance_sth.doctype.deposito.deposito import update_deposito_payment_entry
from sth.finance_sth.doctype.loan_bank.loan_bank import update_loan_bank_payment_entry

def cek_kriteria(self,method):
	if self.references:
		for row in self.references:
			doctype = row.reference_doctype
			docname = row.reference_name

			check = 0
			for row in self.detail_dokumen_finance:
				if row.type == doctype and row.name1 == docname:
					check = 1
			
			if check == 0:
				fill_kriteria(self, doctype, docname)

		# bersih-bersih kalau ada yang tidak di reference
		list_type = []
		list_name = []

		for row in self.references:
			list_type.append(row.reference_doctype)
			list_name.append(row.reference_name)

		self.detail_dokumen_finance = [baris for baris in self.detail_dokumen_finance if baris.type in list_type and baris.name1 in list_name]

def fill_kriteria(self,doctype, docname):
	# ambil dulu dari kriteria
	kriteria = frappe.db.sql(""" SELECT name FROM `tabKriteria Dokumen Finance` WHERE name = "{}" """.format(doctype))
	if len(kriteria) > 0:
		kriteria_doc = frappe.get_doc("Kriteria Dokumen Finance",kriteria[0][0])
		for row in kriteria_doc.kriteria_dokumen_finance:
			if row.aktif == 1:
				self.append("detail_dokumen_finance",{
					"rincian_dokumen_finance": row.rincian_dokumen_finance,
					"type": doctype,
					"name1": docname
				})
			self.append("detail_dokumen_finance",{
				"rincian_dokumen_finance": row.rincian_dokumen_finance
			})

def update_check_book(self, method):
	if self.mode_of_payment != "Cheque" and not self.custom_cheque_number:
		return
	if method == "on_trash":
		delete_cheque_history(self.custom_cheque_number)
		return

	status = {
		"on_submit": "Used",
		"on_cancel": "Void"
	}
	data = frappe._dict({
		"reference_doc": self.doctype,
		"reference_name": self.name,
		"status": status.get(method, "Draft"),
		"cheque_amount": self.paid_amount,
		"issue_date": self.posting_date,
		"note": self.remarks,
		"upload_cheque_book": self.upload_cheque_book
	})
	
	cheque_number = update_cheque_number_pe(self.custom_cheque_number, data)
	update_cheque_book_pe(cheque_number)


def update_status_deposito(self, method):
	update_deposito_payment_entry(self, method)

def update_status_loan_bank(self, method):
    update_loan_bank_payment_entry(self, method)
    

@frappe.whitelist()
def get_outstanding_reference_documents(args, validate=False):
	if isinstance(args, str):
		args = json.loads(args)

	if args.get("party_type") == "Member":
		return

	if not args.get("get_outstanding_invoices") and not args.get("get_orders_to_be_billed"):
		args["get_outstanding_invoices"] = True

	ple = qb.DocType("Payment Ledger Entry")
	common_filter = []
	accounting_dimensions_filter = []
	posting_and_due_date = []

	# confirm that Supplier is not blocked
	if args.get("party_type") == "Supplier":
		supplier_status = get_supplier_block_status(args["party"])
		if supplier_status["on_hold"]:
			if supplier_status["hold_type"] == "All":
				return []
			elif supplier_status["hold_type"] == "Payments":
				if (
					not supplier_status["release_date"]
					or getdate(nowdate()) <= supplier_status["release_date"]
				):
					return []

	party_account_currency = get_account_currency(args.get("party_account"))
	company_currency = frappe.get_cached_value("Company", args.get("company"), "default_currency")

	# Get positive outstanding sales /purchase invoices
	condition = ""
	if args.get("voucher_type") and args.get("voucher_no"):
		condition = " and voucher_type={} and voucher_no={}".format(
			frappe.db.escape(args["voucher_type"]), frappe.db.escape(args["voucher_no"])
		)
		common_filter.append(ple.voucher_type == args["voucher_type"])
		common_filter.append(ple.voucher_no == args["voucher_no"])

	# Add cost center condition
	if args.get("cost_center"):
		condition += " and cost_center='%s'" % args.get("cost_center")
		accounting_dimensions_filter.append(ple.cost_center == args.get("cost_center"))

	# dynamic dimension filters
	active_dimensions = get_dimensions()[0]
	for dim in active_dimensions:
		if args.get(dim.fieldname):
			condition += f" and {dim.fieldname}='{args.get(dim.fieldname)}'"
			accounting_dimensions_filter.append(ple[dim.fieldname] == args.get(dim.fieldname))

	date_fields_dict = {
		"posting_date": ["from_posting_date", "to_posting_date"],
		"due_date": ["from_due_date", "to_due_date"],
	}

	for fieldname, date_fields in date_fields_dict.items():
		if args.get(date_fields[0]) and args.get(date_fields[1]):
			condition += " and {} between '{}' and '{}'".format(
				fieldname, args.get(date_fields[0]), args.get(date_fields[1])
			)
			posting_and_due_date.append(ple[fieldname][args.get(date_fields[0]) : args.get(date_fields[1])])
		elif args.get(date_fields[0]):
			# if only from date is supplied
			condition += f" and {fieldname} >= '{args.get(date_fields[0])}'"
			posting_and_due_date.append(ple[fieldname].gte(args.get(date_fields[0])))
		elif args.get(date_fields[1]):
			# if only to date is supplied
			condition += f" and {fieldname} <= '{args.get(date_fields[1])}'"
			posting_and_due_date.append(ple[fieldname].lte(args.get(date_fields[1])))

	if args.get("company"):
		condition += " and company = {}".format(frappe.db.escape(args.get("company")))
		common_filter.append(ple.company == args.get("company"))

	outstanding_invoices = []
	negative_outstanding_invoices = []

	party_account = args.get("party_account")

	# get party account if advance account is set.
	if args.get("book_advance_payments_in_separate_party_account"):
		accounts = get_party_account(
			args.get("party_type"), args.get("party"), args.get("company"), include_advance=True
		)
		advance_account = accounts[1] if len(accounts) > 1 else None

		if party_account == advance_account:
			party_account = accounts[0]

	if args.get("get_outstanding_invoices"):
		outstanding_invoices = get_outstanding_invoices(
			args.get("party_type"),
			args.get("party"),
			[party_account],
			common_filter=common_filter,
			posting_date=posting_and_due_date,
			min_outstanding=args.get("outstanding_amt_greater_than"),
			max_outstanding=args.get("outstanding_amt_less_than"),
			accounting_dimensions=accounting_dimensions_filter,
			vouchers=args.get("vouchers") or None,
		)

		outstanding_invoices = split_invoices_based_on_payment_terms(
			outstanding_invoices, args.get("company")
		)

		for d in outstanding_invoices:
			d["exchange_rate"] = 1
			if party_account_currency != company_currency:
				if d.voucher_type in frappe.get_hooks("invoice_doctypes"):
					d["exchange_rate"] = frappe.db.get_value(d.voucher_type, d.voucher_no, "conversion_rate")
				elif d.voucher_type == "Journal Entry":
					d["exchange_rate"] = get_exchange_rate(
						party_account_currency, company_currency, d.posting_date
					)
			if d.voucher_type in ("Purchase Invoice"):
				d["bill_no"] = frappe.db.get_value(d.voucher_type, d.voucher_no, "bill_no")

		# Get negative outstanding sales /purchase invoices
		if args.get("party_type") != "Employee":
			negative_outstanding_invoices = get_negative_outstanding_invoices(
				args.get("party_type"),
				args.get("party"),
				args.get("party_account"),
				party_account_currency,
				company_currency,
				condition=condition,
			)

	# Get all SO / PO which are not fully billed or against which full advance not paid
	orders_to_be_billed = []
	if args.get("get_orders_to_be_billed"):
		orders_to_be_billed = get_orders_to_be_billed(
			args.get("posting_date"),
			args.get("party_type"),
			args.get("party"),
			args.get("company"),
			party_account_currency,
			company_currency,
			filters=args,
		)

	data = negative_outstanding_invoices + outstanding_invoices + orders_to_be_billed

	if not data:
		if args.get("get_outstanding_invoices") and args.get("get_orders_to_be_billed"):
			ref_document_type = "invoices or orders"
		elif args.get("get_outstanding_invoices"):
			ref_document_type = "invoices"
		elif args.get("get_orders_to_be_billed"):
			ref_document_type = "orders"

		if not validate:
			frappe.msgprint(
				_(
					"No outstanding {0} found for the {1} {2} which qualify the filters you have specified."
				).format(
					_(ref_document_type), _(args.get("party_type")).lower(), frappe.bold(args.get("party"))
				)
			)

	for i, row in enumerate(data):
		unit_trans = frappe.db.get_value(row.voucher_type, row.voucher_no, "unit")
		if not unit_trans or unit_trans != args.get("unit"):
			del data[i]

	return data