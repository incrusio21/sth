# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _, scrub, unscrub
from frappe.utils import flt, formatdate
from frappe.model.document import Document

import erpnext
from erpnext.utilities.regional import temporary_flag
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
	get_accounting_dimensions,
)
from erpnext.accounts.utils import (
	QueryPaymentLedger,
	get_account_currency,
	get_fiscal_years,
)
from erpnext.controllers.accounts_controller import (
	set_balance_in_account_currency,
	update_gl_dict_with_app_based_fields, 
	update_gl_dict_with_regional_fields
)

from sth.hr_customize import get_payment_settings

class AccountsController(Document):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._party_type = "Employee"
        self._expense_account = "salary_account"
        self._party_account_field = "credit_to"

    def validate(self):
        self.validate_credit_to_acc()
        self.set_outstanding_amount()

    def validate_credit_to_acc(self):
        if not self.meta.has_field(self._party_account_field):
            return
        
        # if not self.credit_to:
        #     self.credit_to = get_party_account("Supplier", self.supplier, self.company)
        #     if not self.credit_to:
        #         self.raise_missing_debit_credit_account_error("Supplier", self.supplier)

        account = frappe.get_cached_value(
            "Account", self.credit_to, ["account_type", "report_type", "account_currency"], as_dict=True
        )

        if account.report_type != "Balance Sheet":
            frappe.throw(
                _(
                    "Please ensure that the {0} account is a Balance Sheet account. You can change the parent account to a Balance Sheet account or select a different account."
                ).format(frappe.bold(_("Credit To"))),
                title=_("Invalid Account"),
            )

        account_type = "Payable" if self._party_account_field == "credit_to" else "Receivable"
        if self.employee and account.account_type != account_type:
            frappe.throw(
                _(
                    "Please ensure that the {0} account {1} is a {2} account. " \
                    "You can change the account type to {2} or select a different account."
                ).format(
                    frappe.bold(_(unscrub(self._party_account_field))), 
                    frappe.bold(self.credit_to),
                    account_type
                ), 
                title=_("Invalid Account"),
            )

        self.party_account_currency = account.account_currency
            
    def set_missing_value(self):
        self.employee = get_payment_settings("internal_employee") or ""
            
    def set_outstanding_amount(self):
        if self.meta.has_field("outstanding_amount"):
            self.outstanding_amount = flt(self.grand_total)

    def on_cancel(self):
        self.ignore_linked_doctypes = (
            "GL Entry",
            "Repost Payment Ledger",
            "Repost Payment Ledger Items",
            "Repost Accounting Ledger",
            "Repost Accounting Ledger Items",
            "Unreconcile Payment",
            "Unreconcile Payment Entries",
            "Payment Ledger Entry",
        )
            
    def on_trash(self):
        # delete sl and gl entries on deletion of transaction
        if frappe.db.get_single_value("Accounts Settings", "delete_linked_ledger_entries"):

            ple = frappe.qb.DocType("Payment Ledger Entry")
            frappe.qb.from_(ple).delete().where(
                (ple.voucher_type == self.doctype) & (ple.voucher_no == self.name)
                | (
                    (ple.against_voucher_type == self.doctype)
                    & (ple.against_voucher_no == self.name)
                    & ple.delinked
                    == 1
                )
            ).run()

            gle = frappe.qb.DocType("GL Entry")
            frappe.qb.from_(gle).delete().where(
                (gle.voucher_type == self.doctype) & (gle.voucher_no == self.name)
            ).run()
            sle = frappe.qb.DocType("Stock Ledger Entry")
            frappe.qb.from_(sle).delete().where(
                (sle.voucher_type == self.doctype) & (sle.voucher_no == self.name)
            ).run()
                
    def make_gl_entry(self, gl_entries=None):
        from erpnext.accounts.general_ledger import make_gl_entries, make_reverse_gl_entries

        if not gl_entries:
            gl_entries = self.get_gl_entries()

        if self.docstatus == 1:
            make_gl_entries(
                gl_entries,
                merge_entries=False,
            )
        elif self.docstatus == 2:
            make_reverse_gl_entries(voucher_type=self.doctype, voucher_no=self.name)
            
        update_voucher_outstanding(
            self.doctype,
            self.name,
            self.credit_to,
            self._party_type,
            self.get(scrub(self._party_type))
        )

    def get_gl_entries(self):
        gl_entries = []

        self.make_party_gl_entry(gl_entries)
        self.make_salary_gl_entry(gl_entries)

        return gl_entries

    def make_party_gl_entry(self, gl_entries):
        credit_or_debit = "credit" if self._party_account_field == "credit_to" else "debit"
        gl_entries.append(
            self.get_gl_dict(
                {
                    "account": self.get(self._party_account_field),
                    "against": self.get(self._expense_account),
                    credit_or_debit: self.grand_total,
                    f"{credit_or_debit}_in_account_currency": self.grand_total,
                    "cost_center": self.cost_center,
                    "party_type": self._party_type,
                    "party": self.get(scrub(self._party_type)),
                    "against_voucher": self.name,
                    "against_voucher_type": self.doctype,	
                },
                item=self,
            )
        )

    def make_salary_gl_entry(self, gl_entries):
        cost_center = erpnext.get_default_cost_center(self.company)
        credit_or_debit = "credit" if self._party_account_field != "credit_to" else "debit"

        gl_entries.append(
            self.get_gl_dict(
                {
                    "account": self.get(self._expense_account),
                    "against": self.get(scrub(self._party_type)) or self.credit_to,
                    credit_or_debit: self.grand_total,
                    f"{credit_or_debit}_in_account_currency": self.grand_total,
                    "cost_center": cost_center		
                },
                item=self,
            )
        )

    def get_gl_dict(self, args, account_currency=None, item=None):
        """this method populates the common properties of a gl entry record"""

        posting_date = args.get("posting_date") or self.get("posting_date")
        fiscal_years = get_fiscal_years(posting_date, company=self.company)
        if len(fiscal_years) > 1:
            frappe.throw(
                ("Multiple fiscal years exist for the date {0}. Please set company in Fiscal Year").format(
                    formatdate(posting_date)
                )
            )
        else:
            fiscal_year = fiscal_years[0][0]

        gl_dict = frappe._dict(
            {
                "company": self.company,
                "posting_date": posting_date,
                "fiscal_year": fiscal_year,
                "voucher_type": self.doctype,
                "voucher_no": self.name,
                "remarks": self.get("remarks") or self.get("remark"),
                "debit": 0,
                "credit": 0,
                "debit_in_account_currency": 0,
                "credit_in_account_currency": 0,
                "is_opening": self.get("is_opening") or "No",
                "party_type": None,
                "party": None,
                "project": self.get("project"),
                "post_net_value": args.get("post_net_value"),
                "voucher_detail_no": args.get("voucher_detail_no"),
            }
        )

        with temporary_flag("company", self.company):
            update_gl_dict_with_regional_fields(self, gl_dict)

        update_gl_dict_with_app_based_fields(self, gl_dict)

        accounting_dimensions = get_accounting_dimensions()
        dimension_dict = frappe._dict()

        for dimension in accounting_dimensions:
            dimension_dict[dimension] = self.get(dimension)
            if item and item.get(dimension):
                dimension_dict[dimension] = item.get(dimension)

        gl_dict.update(dimension_dict)
        gl_dict.update(args)

        if not account_currency:
            account_currency = get_account_currency(gl_dict.account)

        set_balance_in_account_currency(
            gl_dict, account_currency, self.get("conversion_rate"), "IDR"
        )

        if not args.get("against_voucher_type") and self.get("against_voucher_type"):
            gl_dict.update({"against_voucher_type": self.get("against_voucher_type")})

        if not args.get("against_voucher") and self.get("against_voucher"):
            gl_dict.update({"against_voucher": self.get("against_voucher")})

        return gl_dict
	
def update_voucher_outstanding(voucher_type, voucher_no, account, party_type, party):
	ple = frappe.qb.DocType("Payment Ledger Entry")
	vouchers = [frappe._dict({"voucher_type": voucher_type, "voucher_no": voucher_no})]
	common_filter = []
	if account:
		common_filter.append(ple.account == account)

	if party_type:
		common_filter.append(ple.party_type == party_type)

	if party:
		common_filter.append(ple.party == party)

	ple_query = QueryPaymentLedger()

	ref_doc = frappe.get_doc(voucher_type, voucher_no)
	
	# on cancellation outstanding can be an empty list
	voucher_outstanding = ple_query.get_voucher_outstandings(vouchers, common_filter=common_filter)

	outstanding = voucher_outstanding[0]["outstanding_in_account_currency"] if voucher_outstanding else 0
	outstanding_amount = flt(
		outstanding, ref_doc.precision("outstanding_amount")
	)

	# Didn't use db_set for optimisation purpose
	ref_doc.outstanding_amount = outstanding_amount
	frappe.db.set_value(
		voucher_type,
		voucher_no,
		"outstanding_amount",
		outstanding_amount,
	)

	# ref_doc.set_status(update=True)
	ref_doc.notify_update()