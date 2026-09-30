# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

from erpnext.accounts.general_ledger import make_reverse_gl_entries

from sth.controllers.accounts_controller import AccountsController

class BPJSKES(AccountsController):
	"""Dibuat Daftar BPJS saat submit, tanpa jurnal.

	Dulu submit mendebit beban tiap program dan mengkredit hutang BPJS.
	Sekarang tidak lagi; dokumen ini tinggal sebagai dasar Payment Voucher.
	"""

	def validate(self):
		self.set_missing_value()

	def on_cancel(self):
		super().on_cancel()
		# Dokumen lama masih punya GL dari submit dulu, itu yang dibalik.
		# Dokumen baru tidak punya GL, pemanggilan ini tidak berbuat apa-apa.
		make_reverse_gl_entries(voucher_type=self.doctype, voucher_no=self.name)
