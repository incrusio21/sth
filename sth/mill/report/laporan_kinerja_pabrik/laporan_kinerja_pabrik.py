# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data

def get_columns(filters):
	columns = [
		{
			"label": _("URAIAN"),
			"fieldname": "uraian",
			"fieldtype": "Data",
		},
		{
			"label": _("UOM"),
			"fieldname": "uom",
			"fieldtype": "Data",
		},
		{
			"label": _("BOBOT"),
			"fieldname": "bobot",
			"fieldtype": "Float",
		},
	]

	months = [
		"Jan", "Feb", "Mar", "Apr", "May", "Jun",
		"Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
	]

	from_idx = months.index(filters.get("from_month"))
	to_idx = months.index(filters.get("to_month"))

	selected_months = months[from_idx:to_idx + 1]

	for month in selected_months:
		columns.extend([
			{
				"label": _(f"{month.upper()} Aktual"),
				"fieldname": f"{month.lower()}_aktual",
				"fieldtype": "Currency",
				"width": 120,
			},
			{
				"label": _(f"{month.upper()} Budget"),
				"fieldname": f"{month.lower()}_budget",
				"fieldtype": "Currency",
				"width": 120,
			},
			{
				"label": _(f"{month.upper()} Var(%)"),
				"fieldname": f"{month.lower()}_var",
				"fieldtype": "Percent",
				"width": 100,
			},
		])
 
	return columns

def get_data(filters):
	data = []
 
	data.append({
		"uraian": "2025-05"
	})

	return data