# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

# Urutannya sekaligus urutan tampil di report: bengkel dulu karena hasilnya
# dipakai mill dan kebun, sama dengan urutan COSTING_OTOMATIS di
# sth/overrides/accounting_period.py.
COSTING_DOCTYPES = (
	"Costing Bengkel",
	"Costing Mill",
	"Costing Panen",
	"Costing Perawatan",
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	periode = get_periode(filters)
	dokumen = get_dokumen_costing(periode, filters)
	return get_columns(), get_data(periode, dokumen, filters)


def get_periode(filters):
	"""Accounting Period jadi patokan: company, unit dan rentang tanggalnya
	diambil dari sana, bukan dari filter yang bisa diubah user."""
	if not filters.get("accounting_period"):
		frappe.throw(_("Accounting Period wajib diisi."))

	periode = frappe.db.get_value(
		"Accounting Period",
		filters.accounting_period,
		["name", "company", "unit", "start_date", "end_date"],
		as_dict=True,
	)

	if not periode:
		frappe.throw(_("Accounting Period {0} tidak ditemukan.").format(filters.accounting_period))

	return periode


def get_dokumen_costing(periode, filters):
	"""Costing milik periode ini, per doctype.

	Costing tidak menyimpan link ke Accounting Period; kaitannya lewat
	company + unit + rentang periode yang persis sama, cara yang sama dipakai
	create_costing_on_submit waktu membuatnya.
	"""
	jenis = filters.get("jenis_costing") or COSTING_DOCTYPES
	if isinstance(jenis, str):
		jenis = [jenis]

	dokumen = {}

	for doctype in COSTING_DOCTYPES:
		if doctype not in jenis:
			continue

		costing_filters = {
			"company": periode.company,
			"periode_dari": periode.start_date,
			"periode_sampai": periode.end_date,
			"docstatus": 1,
		}
		if periode.unit:
			costing_filters["unit"] = periode.unit

		nama = frappe.get_all(doctype, filters=costing_filters, pluck="name", order_by="name")
		if nama:
			dokumen[doctype] = nama

	return dokumen


def get_gl_entries(periode, dokumen, filters):
	conditions = []
	values = {"company": periode.company}

	pasangan = []
	for i, (doctype, nama) in enumerate(dokumen.items()):
		key_type = "vt{0}".format(i)
		key_no = "vn{0}".format(i)
		values[key_type] = doctype
		values[key_no] = nama
		pasangan.append(
			"(gle.voucher_type = %({0})s AND gle.voucher_no IN %({1})s)".format(key_type, key_no)
		)

	conditions.append("(" + " OR ".join(pasangan) + ")")

	if filters.get("account"):
		conditions.append("gle.account IN %(account)s")
		values["account"] = filters.get("account")

	if filters.get("cost_center"):
		conditions.append("gle.cost_center IN %(cost_center)s")
		values["cost_center"] = filters.get("cost_center")

	return frappe.db.sql(
		"""
		SELECT gle.voucher_type, gle.voucher_no, gle.posting_date,
			gle.account, gle.cost_center, gle.remarks,
			gle.debit, gle.credit
		FROM `tabGL Entry` gle
		WHERE gle.is_cancelled = 0
			AND gle.company = %(company)s
			AND {conditions}
		ORDER BY gle.voucher_no, gle.account, gle.debit DESC
	""".format(conditions=" AND ".join(conditions)),
		values,
		as_dict=True,
	)


def get_data(periode, dokumen, filters):
	if not dokumen:
		return []

	entries = get_gl_entries(periode, dokumen, filters)

	per_dokumen = {}
	for gle in entries:
		per_dokumen.setdefault(gle.voucher_no, []).append(gle)

	data = []
	grand_debit = 0
	grand_credit = 0

	for doctype in COSTING_DOCTYPES:
		for voucher_no in dokumen.get(doctype, []):
			baris = per_dokumen.get(voucher_no)
			if not baris:
				continue

			total_debit = 0
			total_credit = 0

			for gle in baris:
				total_debit += flt(gle.debit)
				total_credit += flt(gle.credit)
				data.append({
					"voucher_type": gle.voucher_type,
					"voucher_no": gle.voucher_no,
					"posting_date": gle.posting_date,
					"account": gle.account,
					"cost_center": gle.cost_center,
					"keterangan": gle.remarks,
					"debit": flt(gle.debit),
					"credit": flt(gle.credit),
				})

			grand_debit += total_debit
			grand_credit += total_credit

			data.append({
				"voucher_type": doctype,
				"keterangan": _("Total {0}").format(voucher_no),
				"debit": total_debit,
				"credit": total_credit,
				"is_total": 1,
			})

	# Total keseluruhan ditulis sendiri, bukan lewat add_total_row: baris subtotal
	# per dokumen di atas ikut terjumlah kalau add_total_row yang dipakai.
	if data:
		data.append({
			"keterangan": _("Total Seluruh Costing"),
			"debit": grand_debit,
			"credit": grand_credit,
			"is_total": 1,
		})

	return data


def get_columns():
	return [
		{
			"label": _("Jenis Costing"),
			"fieldname": "voucher_type",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("No Dokumen"),
			"fieldname": "voucher_no",
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 160,
		},
		{
			"label": _("Tanggal"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 100,
		},
		{
			"label": _("Akun"),
			"fieldname": "account",
			"fieldtype": "Link",
			"options": "Account",
			"width": 300,
		},
		{
			"label": _("Cost Center"),
			"fieldname": "cost_center",
			"fieldtype": "Link",
			"options": "Cost Center",
			"width": 240,
		},
		{
			"label": _("Keterangan"),
			"fieldname": "keterangan",
			"fieldtype": "Data",
			"width": 280,
		},
		{
			"label": _("Debit"),
			"fieldname": "debit",
			"fieldtype": "Currency",
			"width": 140,
		},
		{
			"label": _("Kredit"),
			"fieldname": "credit",
			"fieldtype": "Currency",
			"width": 140,
		},
	]
