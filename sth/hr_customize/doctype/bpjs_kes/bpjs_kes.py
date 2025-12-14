# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe, erpnext

from frappe.model.document import Document
from sth.controllers.accounts_controller import AccountsController

from erpnext.accounts.general_ledger import merge_similar_entries
class BPJSTK(AccountsController):
	def on_submit(self):
		self.make_gl_entry()

	def on_cancel(self):
		super().on_cancel()
		self.make_gl_entry()

	def get_gl_entries(self):
		gl_entries = []

		self.make_bpjs_expense_gl_entry(gl_entries)
		self.make_bpjs_credit_gl_entry(gl_entries)

		gl_entries = merge_similar_entries(gl_entries)

		return gl_entries

	def make_bpjs_expense_gl_entry(self, gl_entries):
		cost_center = erpnext.get_default_cost_center(self.company)
		credit_or_debit = "debit"

		daftar_bpjs = frappe.get_doc("Daftar BPJS", self.no_daftar_bpjs)
		setup_bpjs = frappe.get_doc("Set Up BPJS PT", daftar_bpjs.set_up_bpjs)

		for program in setup_bpjs.set_up_bpjs_pt_table:
			nama_program = program.nama_program
			jumlah = 0
			for daftar in daftar_bpjs.set_up_bpjs_detail_table:
				if daftar.program == nama_program: 
					jumlah += daftar.beban_karyawan + daftar.beban_perusahaan

			gl_entries.append(
				self.get_gl_dict(
					{
						"account": program.expense_account,
						"against": self.credit_account,
						credit_or_debit: jumlah,
						f"{credit_or_debit}_in_account_currency": jumlah,
						"cost_center": cost_center		
					},
					item=self,
				)
			)

	def make_bpjs_credit_gl_entry(self, gl_entries):
		cost_center = erpnext.get_default_cost_center(self.company)
		credit_or_debit = "credit"
		gl_entries.append(
			self.get_gl_dict(
				{
					"account": self.credit_account,
					credit_or_debit: self.grand_total,
					f"{credit_or_debit}_in_account_currency": self.grand_total,
					"cost_center": cost_center		
				},
				item=self,
			)
		)