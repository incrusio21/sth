# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from decimal import Decimal

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []
 
	unit = frappe.db.get_value("Unit", filters.get("unit"), "*")
	if(filters.get("kas_bank") == "Kas"):
		account = frappe.db.get_value("Unit", filters.get("unit"), "account_for_cash")
	elif(filters.get("kas_bank") == "Bank"):
		account = frappe.db.get_value("Unit", filters.get("unit"), "bank_account")
	
	# 1. Dapatkan opening debit, credit, dan balance
	opening_debit, opening_credit, opening_balance = get_opening_balance_detail(filters, account)
	
	# 2. Dapatkan data transaksi dalam periode
	query_l_harian_kas_dan_bank = frappe.db.sql("""
		SELECT
		gle.posting_date as tanggal,
		'' as rekening_bank,
		gle.voucher_no as no_transaksi,
		'' as keterangan,
		gle.debit as penerimaan,
		gle.credit as pengeluaran,
		0 as saldo,
		pe.reference_no as no_ref_bank
		FROM `tabGL Entry` as gle
		LEFT JOIN `tabPayment Entry` as pe ON pe.name = gle.voucher_no
		WHERE gle.account = %(account)s AND
		gle.posting_date >= %(start_date)s AND gle.posting_date <= %(end_date)s
		AND gle.is_cancelled = 0
		ORDER BY gle.posting_date;
  	""", {
			'account': account,
  		'start_date': filters.get('from_date'),
  		'end_date': filters.get('to_date')
  	}, as_dict=True)

	# 3. Tambahkan opening balance sebagai baris pertama dengan debit dan credit
	opening_row = {
		'tanggal': '',
		'rekening_bank': 'Opening',
		'no_transaksi': '',
		'keterangan': '',
		'penerimaan': opening_debit,
		'pengeluaran': opening_credit,
		'saldo': opening_balance,
		'no_ref_bank': ''
	}
	data.append(opening_row)

	# 4. Hitung running balance untuk setiap transaksi
	running_balance = opening_balance
	for row in query_l_harian_kas_dan_bank:
		penerimaan = row['penerimaan'] or 0
		pengeluaran = row['pengeluaran'] or 0
		
		# Hitung balance: debit (penerimaan) + kredit (pengeluaran)
		# Asumsi: Debit = plus, Kredit = minus
		running_balance = running_balance + penerimaan - pengeluaran
		
		row['rekening_bank'] = unit.default_bank_account
		row['saldo'] = running_balance
		data.append(row)

	# 5. Hitung total debit dan kredit
	total_penerimaan = sum([row.get('penerimaan', 0) or 0 for row in query_l_harian_kas_dan_bank])
	total_pengeluaran = sum([row.get('pengeluaran', 0) or 0 for row in query_l_harian_kas_dan_bank])

	# 6. Tambahkan baris total
	total_row = {
		'tanggal': '',
		'rekening_bank': 'Total',
		'no_transaksi': '',
		'keterangan': '',
		'penerimaan': total_penerimaan,
		'pengeluaran': total_pengeluaran,
		'saldo': opening_balance + total_penerimaan - total_pengeluaran,
		'no_ref_bank': ''
	}
	data.append(total_row)

	# 7. Tambahkan baris closing (opening + total)
	closing_balance = opening_balance + total_penerimaan - total_pengeluaran
	closing_row = {
		'tanggal': '',
		'rekening_bank': 'Closing (Opening + Total)',
		'no_transaksi': '',
		'keterangan': '',
		'penerimaan': opening_debit + total_penerimaan,
		'pengeluaran': opening_credit + total_pengeluaran,
		'saldo': closing_balance,
		'no_ref_bank': ''
	}
	data.append(closing_row)

	return columns, data


def get_opening_balance_detail(filters, account):
	result = frappe.db.sql("""
		SELECT
		COALESCE(SUM(gle.debit), 0) as total_debit,
		COALESCE(SUM(gle.credit), 0) as total_credit
		FROM `tabGL Entry` as gle
		WHERE gle.account = %(account)s
		AND gle.posting_date < %(start_date)s
		AND gle.is_cancelled = 0
	""", {
		'account': account,
		'start_date': filters.get('from_date')
	}, as_dict=True)

	if result:
		total_debit = result[0].get('total_debit', 0) or 0
		total_credit = result[0].get('total_credit', 0) or 0
		opening_balance = total_debit - total_credit
		return total_debit, total_credit, opening_balance
	
	return 0, 0, 0

def get_condition(filters):
	conditions = ""
	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("Tanggal"),
			"fieldtype": "Date",
			"fieldname": "tanggal",
			"width": 120
		},
		{
			"label": _("Rekening Bank"),
			"fieldtype": "Data",
			"fieldname": "rekening_bank",
			"width": 200
		},
		{
			"label": _("No Transaksi"),
			"fieldtype": "Data",
			"fieldname": "no_transaksi",
   		"width": 200
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