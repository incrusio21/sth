import frappe
from frappe.utils import (
	add_days,
	add_months,
	cint,
	comma_and,
	flt,
	fmt_money,
	formatdate,
	get_last_day,
	get_link_to_form,
	getdate,
	nowdate,
	parse_json,
	today,
)

import erpnext
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
	get_accounting_dimensions,
	get_dimensions,
)
from erpnext.accounts.doctype.pricing_rule.utils import (
	apply_pricing_rule_for_free_items,
	apply_pricing_rule_on_transaction,
	get_applied_pricing_rules,
)
from erpnext.accounts.general_ledger import get_round_off_account_and_cost_center
from erpnext.accounts.party import (
	get_party_account,
	get_party_account_currency,
	get_party_gle_currency,
	validate_party_frozen_disabled,
)
from erpnext.accounts.utils import (
	create_gain_loss_journal,
	get_account_currency,
	get_currency_precision,
	get_fiscal_years,
	validate_fiscal_year,
)
from erpnext.accounts.utils import (
	get_advance_payment_doctypes as _get_advance_payment_doctypes,
)
from erpnext.buying.utils import update_last_purchase_rate
from erpnext.controllers.print_settings import (
	set_print_templates_for_item_table,
	set_print_templates_for_taxes,
)
from erpnext.controllers.sales_and_purchase_return import validate_return
from erpnext.exceptions import InvalidCurrency
from erpnext.setup.utils import get_exchange_rate
from erpnext.stock.doctype.item.item import get_uom_conv_factor
from erpnext.stock.doctype.packed_item.packed_item import make_packing_list
from erpnext.stock.get_item_details import (
	_get_item_tax_template,
	get_conversion_factor,
	get_item_details,
	get_item_tax_map,
	get_item_warehouse,
)
from erpnext.utilities.regional import temporary_flag
from erpnext.utilities.transaction_base import TransactionBase
from erpnext.controllers.accounts_controller import set_balance_in_account_currency,update_gl_dict_with_regional_fields,update_gl_dict_with_app_based_fields


@frappe.whitelist()
def test_buat_gl():
	doc = frappe.get_doc("Pengajuan Panen Kontanan","PPK-00174")
	master_pembuatan_gl_dan_pl(doc,"validate")

@frappe.whitelist()
def master_pembuatan_gl_dan_pl(doc,method):
	# menentukan pembuatan gl
	akun_debit = ""
	akun_credit = ""
	nilai_debit = ""
	nilai_credit = ""

	if doc.doctype == "Pengajuan Panen Kontanan":
		akun_debit = doc.get("salary_account")
		akun_credit = doc.get("paid_account")
		nilai_debit = doc.get("grand_total")
		nilai_credit = doc.get("grand_total")

	pembuatan_gl_entry(doc,akun_debit, akun_credit, nilai_debit, nilai_credit)

@frappe.whitelist()
def pembuatan_gl_entry(self,akun_debit, akun_credit, nilai_debit, nilai_credit):
	from erpnext.accounts.general_ledger import make_gl_entries, make_reverse_gl_entries
	gl_entries = []
	gl_entries.append(
		get_gl_dict(self,
			{
				"account": akun_debit,
				"against": akun_credit,
				"debit": nilai_debit,
				"debit_in_account_currency": nilai_debit,
				"cost_center": "Main - TML"		
			},
			item=self,
		)
	)

	gl_entries.append(
		get_gl_dict(self,
			{
				"account": akun_credit,
				"against": akun_debit,
				"credit": nilai_debit,
				"credit_in_account_currency": nilai_debit,
				"cost_center": "Main - TML"			
			},
			item=self,
		)
	)

	if self.docstatus == 1:
		make_gl_entries(
			gl_entries,
			merge_entries=False,
		)
	elif self.docstatus == 2:
		make_reverse_gl_entries(voucher_type=self.doctype, voucher_no=self.name)

@frappe.whitelist()
def pembuatan_pl_entry(doc,method):
	pass

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


	if gl_dict.account and self.doctype not in [
		"Journal Entry",
		"Period Closing Voucher",
		"Payment Entry",
	]:
		set_balance_in_account_currency(
			gl_dict, account_currency, self.get("conversion_rate"), "IDR"
		)

	
	if not args.get("against_voucher_type") and self.get("against_voucher_type"):
		gl_dict.update({"against_voucher_type": self.get("against_voucher_type")})

	if not args.get("against_voucher") and self.get("against_voucher"):
		gl_dict.update({"against_voucher": self.get("against_voucher")})

	return gl_dict
