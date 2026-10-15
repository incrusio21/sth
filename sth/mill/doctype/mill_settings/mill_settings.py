# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class MillSettings(Document):
	def validate(self):
		self.validate_akun_difference()

	def validate_akun_difference(self):
		sudah = set()
		for row in self.akun_difference:
			if row.company in sudah:
				frappe.throw(_("Baris {0}: Company {1} sudah punya Akun Difference di baris lain.").format(
					row.idx, frappe.bold(row.company)))
			sudah.add(row.company)

			akun = frappe.db.get_value("Account", row.account, ["company", "is_group"], as_dict=True)
			if akun.company != row.company:
				frappe.throw(_("Baris {0}: Akun {1} bukan milik company {2}.").format(
					row.idx, frappe.bold(row.account), frappe.bold(row.company)))
			if akun.is_group:
				frappe.throw(_("Baris {0}: Akun {1} adalah akun grup.").format(
					row.idx, frappe.bold(row.account)))


def get_akun_difference(company):
	"""Akun difference Stock Entry Data TBS, Sounding CPO dan Sounding PK
	untuk company ini, atau None kalau belum diatur. Kalau None, akunnya
	dibiarkan diisi bawaan ERPNext (Item Default lalu Stock Adjustment Account
	company)."""
	return frappe.db.get_value(
		"Akun Difference Mill",
		{"parent": "Mill Settings", "parenttype": "Mill Settings", "company": company},
		"account",
	)
