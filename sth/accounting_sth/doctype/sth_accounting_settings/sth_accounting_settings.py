# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class STHAccountingSettings(Document):
	pass


@frappe.whitelist()
def get_akun_penjualan_asset(company):
	"""Akun piutang dan expense untuk Sales Invoice penjualan asset (Disposal)."""
	settings = frappe.get_doc("STH Accounting Settings")
	row = next(
		(d for d in settings.sth_accounting_settings_penjualan_asset if d.company == company),
		None
	)

	if not row:
		return {}

	return {
		"piutang_account": row.piutang_account,
		"expense_account": row.expense_account,
	}
