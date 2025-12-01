# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt

from sth.controllers.accounts_controller import AccountsController

class GantiRugiLahan(AccountsController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._expense_account = "expense_account"

	def validate(self):
		self.set_missing_value()
		self.fetch_sppt_data()
		self.calculate_total()
		super().validate()

	@frappe.whitelist()
	def fetch_sppt_data(self):
		self.pemilik_lahan = self.qty = None
		# kosongkan biaya surat jika bukan pembayaran tipe lahan
		if self.pembayaran_lahan not in ("Lahan"):
			self.biaya_surat = 0

		if not self.sppt:
			return
		
		fields = ["pemilik_lahan"]
		if self.pembayaran_lahan == "Lahan":
			fields.append("total_lahan")
		else:
			fields.append("luas_tanam")

		self.pemilik_lahan, self.qty = frappe.db.get_value("GIS", self.sppt, fields)

	def calculate_total(self):
		self.grand_total = flt(self.qty) * flt(self.rate) + flt(self.biaya_surat)

	def on_submit(self):
		self.make_gl_entry()

	def on_cancel(self):
		super().on_cancel()
		self.make_gl_entry()
		
@frappe.whitelist()
def fetch_company_account(company, jenis_biaya=None):
	accounts_dict = {
		"credit_to": frappe.get_cached_value("Company", company, "ganti_rugi_lahan_account"),
	}

	if jenis_biaya:
		accounts_dict["expense_account"] = frappe.db.get_value("Account Ganti Rugi Lahan", {"parent": jenis_biaya, "company": company}, "account")

	return accounts_dict