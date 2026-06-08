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
			"label": _("Tanggal"),
			"fieldname": "tanggal",
			"fieldtype": "Data",
		},
		{
			"label": _("Panjang Mtr"),
			"fieldname": "panjang_mtr",
			"fieldtype": "Data",
		},
		{
			"label": _("STD Utilitas"),
			"fieldname": "std_utilitas",
			"fieldtype": "Data",
		},
		{
			"label": _("ACT Utilitas"),
			"fieldname": "act_utilitas",
			"fieldtype": "Data",
		},
		{
			"label": _("% Utilitas"),
			"fieldname": "percent_utilitas",
			"fieldtype": "Data",
		},
		{
			"label": _("ITEM TBS Olah"),
			"fieldname": "item_tbs_olah",
			"fieldtype": "Data",
		},
		{
			"label": _("ITEM Jam Olah"),
			"fieldname": "item_jam_olah",
			"fieldtype": "Data",
		},
		{
			"label": _("ITEM Kapasitas"),
			"fieldname": "item_kapasitas",
			"fieldtype": "Data",
		},
	]
 
	return columns

def get_data(filters):
	data = []
 
	data.append({
		"tanggal": "1"
	})

	return data