# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt

from sth.controllers.accounts_controller import AccountsController

class PengajuanPembayaran(AccountsController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._expense_account = "expense_account"

	def validate(self):
		self.set_missing_value()
		self.calculate_total()

		super().validate()

	def calculate_total(self):
		totals = 0
		for d in self.details:
			totals += flt(d.amount)
		
		self.grand_total = flt(totals, self.precision("grand_total"))
		
	def on_submit(self):
		self.make_gl_entry()

	def on_cancel(self):
		super().on_cancel()
		self.make_gl_entry()

@frappe.whitelist()
def fetch_company_account(company):
	accounts_dict = {
		"credit_to": frappe.get_cached_value("Company", company, "pengajuan_pembayaran_account"),
	}

	return accounts_dict