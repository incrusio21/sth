# Copyright (c) 2025, [Your Company] and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_columns():
	"""Define the 3 columns for the report"""
	return [
		{
			"fieldname": "unit",
			"label": _("PT"),
			"fieldtype": "Data",
			"width": 200
		},
		{
			"fieldname": "currency",
			"label": _("Mata Uang"),
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "deposit_amount",
			"label": _("Nominal"),
			"fieldtype": "Currency",
			"width": 150
		}
	]

def get_data(filters):
	"""
	Fetch data from Deposito doctype
	Group by unit and currency
	Add total row at the bottom
	"""
	
	# Query to get grouped data
	data = frappe.db.sql("""
		SELECT 
			unit,
			currency,
			SUM(deposit_amount) as deposit_amount
		FROM 
			`tabDeposito`
		GROUP BY 
			unit, currency
		ORDER BY 
			unit, currency
	""", as_dict=1)
	
	# Calculate grand total
	total = 0
	for row in data:
		total += row.get('deposit_amount', 0)
	
	if data:
		data.append({
			'unit': '<b>Total</b>',
			'currency': '',
			'deposit_amount': total
		})
	
	return data