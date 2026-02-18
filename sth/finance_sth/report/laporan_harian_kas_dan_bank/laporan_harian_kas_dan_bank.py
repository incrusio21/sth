# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from erpnext.accounts.utils import get_balance_on
from frappe.utils import nowdate

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []

	query_l_harian_kas_dan_bank = frappe.db.sql("""
		SELECT 
		pe.posting_date as tanggal,
		pe.bank_account_no as rekening_bank,
		pe.name as no_transaksi,
		pe.note as keterangan,
		CASE
			WHEN pe.payment_type = "Receive" THEN pe.paid_amount
			ELSE 0
		END as penerimaan,
		CASE
			WHEN pe.payment_type = "Pay" THEN pe.paid_amount
			ELSE 0
		END as pengeluaran,
		pe.reference_no as no_ref_bank,
		ba.account as account
		FROM `tabPayment Entry` as pe
		JOIN `tabBank Account` as ba ON ba.name = pe.bank_account
		WHERE 1 = 1
		{}
		;
  """.format(conditions), as_dict=True, debug=1)

	for payment_entry in query_l_harian_kas_dan_bank:
		pe = payment_entry
		account = payment_entry.get("account")

		if account and frappe.db.exists("Account", account):
			pe["saldo"] = get_balance_on(account=account, date=nowdate())
		else:
			pe["saldo"] = 0

		data.append(pe)
  
	data.append({
		"keterangan": "Jumlah",
		"penerimaan": sum(d.get("penerimaan", 0) for d in data),
		"pengeluaran": sum(d.get("pengeluaran", 0) for d in data),
		"saldo": sum(d.get("saldo", 0) for d in data)
	})

	return columns, data

def get_condition(filters):
	conditions = ""

	# if filters.get("bulan"):
	# 	conditions += " AND DATE_FORMAT(dit.posting_date, '%%b') = %(bulan)s"

	# if filters.get("tahun"):
	# 	conditions += " AND DATE_FORMAT(dit.posting_date, '%%Y') = %(tahun)s"

	# if filters.get("jenis_deposito"):
	# 	conditions += " AND d.deposito_type = %(jenis_deposito)s"

	# if filters.get("status_deposito"):
	# 	conditions += " AND d.is_redeemed = %(status_deposito)s"

	if filters.get("company"):
		conditions += """ AND pe.company = "{}" """.format(filters.get("company"))

	if filters.get("unit"):
		conditions += """ AND pe.unit = "{}" """.format(filters.get("unit"))

	if filters.get("kas_bank") == "Kas":
		conditions += """ AND pe.mode_of_payment = 'Cash' """
	elif filters.get("kas_bank") == "Bank":
		conditions += """ AND pe.mode_of_payment = 'Bank Draft' """

	if filters.get("from_date"):
		conditions += """ AND pe.posting_date >= "{}" """.format(filters.get("from_date"))

	if filters.get("to_date"):
		conditions += """ AND pe.posting_date <= "{}" """.format(filters.get("to_date"))

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("Tanggal"),
			"fieldtype": "Date",
			"fieldname": "tgl",
		},
		{
			"label": _("Rekening Bank"),
			"fieldtype": "Data",
			"fieldname": "rekening_bank",
		},
		{
			"label": _("No Transaksi"),
			"fieldtype": "Data",
			"fieldname": "no_transaksi",
		},
		{
			"label": _("Keterangan"),
			"fieldtype": "Data",
			"fieldname": "keterangan",
		},
		{
			"label": _("Penerimaan"),
			"fieldtype": "Currency",
			"fieldname": "penerimaan",
		},
		{
			"label": _("Pengeluaran"),
			"fieldtype": "Currency",
			"fieldname": "pengeluaran",
		},
		{
			"label": _("Saldo"),
			"fieldtype": "Currency",
			"fieldname": "saldo",
		},
		{
			"label": _("No. Ref Bank"),
			"fieldtype": "Data",
			"fieldname": "no_ref_bank",
		},
	]

	return columns