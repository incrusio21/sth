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
		{"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company"},
		{"label": "Unit", "fieldname": "unit", "fieldtype": "Link", "options": "Unit"},
		{"label": "Bank", "fieldname": "bank", "fieldtype": "Data", "options": "Bank"},
		{"label": "Rekening", "fieldname": "bank_account", "fieldtype": "Link", "options": "Bank Account"},
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
	data_raw = frappe.db.sql("""
		SELECT
			ps.company,
			ps.unit,
			ps.bank,
			ps.bank_account,
			ps.posting_date,
			ps.movement_balance
		FROM `tabPosisi Saldo` ps
		INNER JOIN (
			SELECT
				company,
				unit,
				bank,
				bank_account,
				MAX(posting_date) AS last_posting_date
			FROM `tabPosisi Saldo`
			WHERE posting_date BETWEEN %(from_date)s AND %(to_date)s
			GROUP BY company, unit, bank, bank_account
		) latest
		ON  ps.company = latest.company
		AND ps.unit = latest.unit
		AND ps.bank = latest.bank
		AND ps.bank_account = latest.bank_account
		AND ps.posting_date = latest.last_posting_date
	""", filters, as_dict=True)


	rows = defaultdict(dict)

	for d in data_raw:
		key = (d.company, d.unit, d.bank, d.bank_account)

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

	return data


def get_date_range(from_date, to_date):
	dates = []
	current = getdate(from_date)

	while current <= getdate(to_date):
		dates.append(current)
		current = add_days(current, 1)

	return dates