# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

# import frappe
from sth.controllers.accounts_controller import AccountsController

class PerhitunganKompensasiPHK(AccountsController):
	def on_submit(self):
		self.make_gl_entry()

	def on_cancel(self):
		super().on_cancel()
		self.make_gl_entry()
