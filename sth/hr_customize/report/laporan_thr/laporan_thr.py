# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []

	data.append({
		"pt": "PT. TRIMITRA LESTARI",
		"rupiah": 100000
	})

	return columns, data

def get_condition(filters):
	conditions = ""

	if filters.get("from_date") and filters.get("to_date"):
		conditions += " AND eg.date BETWEEN %(from_date)s AND %(to_date)s"

	if filters.get("unit"):
		conditions += " AND e.unit = %(unit)s"

	if filters.get("jenis_sp"):
		conditions += " AND eg.grievance_type = %(jenis_sp)s"

	if filters.get("tipe_karyawan"):
		conditions += " AND e.grade = %(tipe_karyawan)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("PT"),
			"fieldtype": "Data",
			"fieldname": "pt",
		},
		{
			"label": _("Unit"),
			"fieldtype": "Data",
			"fieldname": "unit",
		},
		{
			"label": _("Tahun"),
			"fieldtype": "Data",
			"fieldname": "tahun",
		},
		{
			"label": _("THR"),
			"fieldtype": "Data",
			"fieldname": "thr",
		},
		{
			"label": _("KHT"),
			"fieldtype": "Data",
			"fieldname": "kht",
		},
		{
			"label": _("PKWT"),
			"fieldtype": "Data",
			"fieldname": "pkwt",
		},
		{
			"label": _("KHL"),
			"fieldtype": "Data",
			"fieldname": "khl",
		},
		{
			"label": _("Total"),
			"fieldtype": "Data",
			"fieldname": "total",
		},
		{
			"label": _("Rupiah"),
			"fieldtype": "Currency",
			"fieldname": "rupiah",
		},
	]

	return columns