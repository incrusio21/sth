# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

# Kolom akun difference per tipe_barang Item hasil produksi mill.
KOLOM_AKUN_DIFFERENCE = {
	"TBS": "akun_difference_tbs",
	"CPO": "akun_difference_cpo",
	"Palm Kernel": "akun_difference_pk",
}

# Kolom akun persediaan per tipe_barang di tabel COGS.
KOLOM_AKUN_PERSEDIAAN = {
	"TBS": "akun_persediaan_tbs",
	"CPO": "akun_persediaan_cpo",
	"Palm Kernel": "akun_persediaan_pk",
}


class STHAccountingSettings(Document):
	def validate(self):
		self.validate_akun_difference()

	def validate_akun_difference(self):
		sudah = set()
		for row in self.sth_accounting_settings_akun_difference:
			if row.company in sudah:
				frappe.throw(_("Akun Difference Produksi Mill baris {0}: company {1} sudah ada di baris lain.").format(
					row.idx, frappe.bold(row.company)))
			sudah.add(row.company)

			for kolom in KOLOM_AKUN_DIFFERENCE.values():
				akun = row.get(kolom)
				if not akun:
					continue
				company, is_group = frappe.db.get_value("Account", akun, ["company", "is_group"])
				if company != row.company or is_group:
					frappe.throw(_("Akun Difference Produksi Mill baris {0}: {1} harus akun non grup milik {2}.").format(
						row.idx, frappe.bold(akun), frappe.bold(row.company)))


def get_akun_difference(company, tipe_barang):
	"""Difference account Stock Entry yang dibuat Data TBS (TBS), Sounding CPO
	(CPO) dan Sounding Palm Kernel (Palm Kernel) untuk company ini.

	None kalau belum diatur: akunnya lalu diisi bawaan ERPNext, yaitu Item
	Default lalu Stock Adjustment Account company.
	"""
	return frappe.db.get_value(
		"STH Accounting Settings Akun Difference",
		{"parent": "STH Accounting Settings", "company": company},
		KOLOM_AKUN_DIFFERENCE[tipe_barang],
	)


def get_akun_persediaan(company, tipe_barang):
	"""Akun persediaan Item TBS, CPO atau Palm Kernel untuk company ini, dari
	tabel COGS. Akun yang sama dibaca COGS Mill dan Kebun sebagai saldo GL
	persediaan, jadi jurnal stok produk ini harus mendarat di sini.

	None kalau tipe_barang bukan ketiganya atau akunnya belum diatur.
	"""
	kolom = KOLOM_AKUN_PERSEDIAAN.get(tipe_barang)
	if not kolom:
		return None
	return frappe.db.get_value(
		"STH Accounting Settings COGS",
		{"parent": "STH Accounting Settings", "company": company},
		kolom,
	)


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
