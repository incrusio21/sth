# Copyright (c) 2026 DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.utils import flt

from sth.utils.data import tax_rate

def validate_custom_tax(self, method=None):
	self.taxes = []

	tax_list = []
	if self.ppn:
		tax = tax_rate(self.company, self.ppn, "Masukan")
		self.ppn_account = tax["account"]
		self.ppn_rate = tax["rate"]
		self.ppn_amount = flt(self.net_total * (self.ppn_rate / 100))

		if self.ppn_account:
			tax_list.append({
				"account": self.ppn_account,
				"amount": self.ppn_amount
			})
	
	for pph in self.pph_details:
		tax = tax_rate(self.company, pph.type, "PPh")
		pph.account = tax["account"]
		pph.percentage = tax["rate"]
		pph.amount = flt(self.net_total * (pph.percentage / 100))

		if pph.account:
			tax_list.append({
				"account": pph.account,
				"add_deduct": "Deduct",
				"amount": pph.amount
			})

	for t in tax_list:
		self.append("taxes", {
			"category": "Total",
			"description": frappe.get_cached_value("Account", t.get("account"), "account_name"),
			"charge_type": "Actual",
			"add_deduct_tax": t.get("add_deduct") or "Add",
			"account_head": t.get("account"),
			"tax_amount": t.get("amount"),
			"tax_amount": t.get("amount"),
		})


	self.run_method("calculate_taxes_and_totals")

# Penanda yang sama dengan sync_to_taxes di public/js/purchase_invoice.js. GL
# Purchase Invoice hanya membukukan baris taxes yang membawa penanda ini.
PPN_MARKER = "__from_ppn__"
PPH_LAINNYA_MARKER = "__from_pph_lainnya__"

def set_pajak_purchase_invoice(source, target):
	"""Salin PPN dan PPh BAPP/Proposal ke tabel ppn dan pph_lainnya Purchase Invoice.

	Tabel taxes sumber tidak ikut di-map: barisnya tanpa penanda, jadi tidak
	dijurnal, dan ditimpa sync_to_taxes begitu form dibuka.
	"""
	target.pakai_ppn = 1 if source.ppn else 0
	target.set("ppn", [])
	if source.ppn:
		target.append("ppn", {
			"type": source.ppn,
			"tax_type": "PPN",
			"account": source.ppn_account,
			"percentage": source.ppn_rate,
		})

	# Beberapa BAPP bisa digabung ke satu invoice; PPh berjenis sama cukup satu baris
	for pph in source.get("pph_details"):
		if not pph.type or any(d.type == pph.type for d in target.get("pph_lainnya")):
			continue
		target.append("pph_lainnya", {
			"type": pph.type,
			"tax_type": "PPH",
			"account": pph.account,
			"percentage": pph.percentage,
		})

	# Dasar pengenaan sama dengan recalculate_vat_details di purchase_invoice.js
	sub_total = (
		sum(flt(d.amount) for d in target.get("items"))
		+ sum(flt(d.total) for d in target.get("charges_purchase_invoice"))
		- sum(flt(d.amount) for d in target.get("purchase_invoice_pengeluaran_barang"))
	)
	for d in target.get("ppn"):
		d.amount = flt((sub_total - flt(target.jumlah_diskon)) * flt(d.percentage) / 100, d.precision("amount"))
	for d in target.get("pph_lainnya"):
		d.amount = flt(sub_total * flt(d.percentage) / 100, d.precision("amount"))

	target.total_ppn = sum(flt(d.amount) for d in target.get("ppn"))
	target.total_pph_lainnya = sum(flt(d.amount) for d in target.get("pph_lainnya"))

	target.set("taxes", [
		t for t in target.get("taxes")
		if PPN_MARKER not in (t.description or "") and PPH_LAINNYA_MARKER not in (t.description or "")
	])
	for fieldname, marker, sign in (("pph_lainnya", PPH_LAINNYA_MARKER, -1), ("ppn", PPN_MARKER, 1)):
		for d in target.get(fieldname):
			if not d.amount:
				continue
			target.append("taxes", {
				"category": "Total",
				"charge_type": "Actual",
				"add_deduct_tax": "Add",
				"account_head": d.account,
				"tax_amount": d.amount * sign,
				"description": f"{marker}{d.type}",
			})