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
			"label": _("STD/ BGT  B. I"),
			"fieldname": "std_bgt",
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
		columns.append({
			"label": _(f"{month.upper()}"),
			"fieldname": f"{month.lower()}",
			"fieldtype": "Float",
			"width": 120,
		})

	columns.extend([
		{
			"label": _("ACT. YTD"),
			"fieldname": "act_ytd",
			"fieldtype": "Float",
		},
		{
			"label": _("BGT. YTD"),
			"fieldname": "bgt_ytd",
			"fieldtype": "Float",
		},
		{
			"label": _("ANNUAL BGT."),
			"fieldname": "annual_bgt",
			"fieldtype": "Float",
		},
		{
			"label": _("No"),
			"fieldname": "no",
			"fieldtype": "Float",
		},
	])
 
	return columns

def get_data(filters):
	data = []
 
	data.append({
		"uraian": "2025-05"
	})

	return data