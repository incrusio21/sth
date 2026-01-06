# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate, add_days
from collections import defaultdict

def execute(filters=None):
	columns, data = get_columns(filters), get_data(filters)
	return columns, data

def get_columns(filters):
	dates = get_date_range(filters.from_date, filters.to_date)

	columns = [
		{"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 500},
		{"label": "Unit", "fieldname": "unit", "fieldtype": "Link", "options": "Unit", "width": 100},
		{"label": "Bank", "fieldname": "bank", "fieldtype": "Data", "options": "Bank", "width": 150},
		{"label": "Rekening", "fieldname": "bank_account", "fieldtype": "Link", "options": "Bank Account", "width": 200},
	]

	for d in dates:
		columns.append({
			"label": f"Saldo {d.strftime('%d-%m-%Y')}",
			"fieldname": f"saldo_{d.strftime('%Y_%m_%d')}",
			"fieldtype": "Currency"
		})
  
	return columns

def get_data(filters):
	dates = get_date_range(filters.from_date, filters.to_date)
	
	if filters.from_date == filters.to_date:
		data_raw = frappe.db.sql("""
			SELECT
				company,
				unit,
				bank,
				bank_account,
				DATE(posting_date) AS posting_date,
				movement_balance
			FROM (
				SELECT
					ps.company,
					ps.unit,
					ps.bank,
					ps.bank_account,
					ps.posting_date,
					ps.movement_balance,
					ROW_NUMBER() OVER (
						PARTITION BY
							ps.company,
							ps.unit,
							ps.bank,
							ps.bank_account,
							DATE(ps.posting_date)
						ORDER BY ps.posting_date DESC
					) AS rn
				FROM `tabPosisi Saldo` ps
				WHERE DATE(ps.posting_date) = %(from_date)s
			) t
			WHERE rn = 1
			ORDER BY company, bank, bank_account, posting_date
		""", filters, as_dict=True, debug=True)
	else:
		data_raw = frappe.db.sql("""
			SELECT
				company,
				unit,
				bank,
				bank_account,
				DATE(posting_date) AS posting_date,
				movement_balance
			FROM (
				SELECT
					ps.company,
					ps.unit,
					ps.bank,
					ps.bank_account,
					ps.posting_date,
					ps.movement_balance,
					ROW_NUMBER() OVER (
						PARTITION BY
							ps.company,
							ps.unit,
							ps.bank,
							ps.bank_account,
							DATE(ps.posting_date)
						ORDER BY ps.posting_date DESC
					) AS rn
				FROM `tabPosisi Saldo` ps
				WHERE DATE(ps.posting_date) BETWEEN %(from_date)s AND %(to_date)s
			) t
			WHERE rn = 1
			ORDER BY company, bank, bank_account, posting_date
		""", filters, as_dict=True, debug=True)

	rows = defaultdict(dict)

	for d in data_raw:
		key = (d.bank_account)

		if not rows.get(key):
			rows[key] = {
				"company": d.company,
				"unit": d.unit,
				"bank": d.bank,
				"bank_account": d.bank_account,
			}

		field = f"saldo_{d.posting_date.strftime('%Y_%m_%d')}"
		rows[key][field] = d.movement_balance

	data = []

	for row in rows.values():
		for d in dates:
			field = f"saldo_{d.strftime('%Y_%m_%d')}"
			row.setdefault(field, 0)
		data.append(row)
  
	q_penerimaan = frappe.db.sql("""
		SELECT
		SUM(ge.debit) as total
		FROM `tabGL Entry` as ge
		JOIN `tabAccount` as a ON a.name = ge.account
		WHERE a.is_group = 0 AND a.account_type = 'Direct Income' AND ge.posting_date BETWEEN %(from_date)s AND %(to_date)s;
	""", filters, as_dict=True)

	q_pengeluaran = frappe.db.sql("""
		SELECT
		SUM(ge.debit) as total
		FROM `tabGL Entry` as ge
		JOIN `tabAccount` as a ON a.name = ge.account
		WHERE a.is_group = 0 AND a.account_type = 'Payable' AND ge.posting_date BETWEEN %(from_date)s AND %(to_date)s;
	""", filters, as_dict=True)
  
	data.append({
		"company": "ESTIMASI HARIAN DANA MASUK - PENERIMAAN DARI :",
		f"saldo_{dates[-1].strftime('%Y_%m_%d')}": q_penerimaan[0].get("total")
	})

	data.append({
		"company": "ESTIMASI HARIAN DANA KELUAR - PENGELUARAN UNTUK :",
		f"saldo_{dates[-1].strftime('%Y_%m_%d')}":  q_pengeluaran[0].get("total")
	})

	return data


def get_date_range(from_date, to_date):
	dates = []
	current = getdate(from_date)

	while current <= getdate(to_date):
		dates.append(current)
		current = add_days(current, 1)

	return dates[::-1]