# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []
 
	data.append({
		"no_transaksi": "Testing"
	})

	return columns, data

def get_condition(filters):
	conditions = ""

	if filters.get("company"):
		conditions += " AND pi.company = %(company)s"

	if filters.get("unit"):
		conditions += " AND pi.unit = %(unit)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("Tanggal"),
			"fieldtype": "Date",
			"fieldname": "tanggal",
		},
		{
			"label": _("No Transaksi"),
			"fieldtype": "Data",
			"fieldname": "no_transaksi",
		},
		{
			"label": _("NO COA"),
			"fieldtype": "Data",
			"fieldname": "no_coa",
		},
		{
			"label": _("COA DESCRIPTION"),
			"fieldtype": "Data",
			"fieldname": "coa_description",
		},
		{
			"label": _("Keterangan"),
			"fieldtype": "Data",
			"fieldname": "keterangan",
		},
		{
			"label": _("Penerimaan"),
			"fieldtype": "Data",
			"fieldname": "penerimaan",
		},
		{
			"label": _("Pengeluaran"),
			"fieldtype": "Data",
			"fieldname": "pengeluaran",
		},
		{
			"label": _("Saldo"),
			"fieldtype": "Currency",
			"fieldname": "saldo",
		},
		{
			"label": _("PDO CATEGORY"),
			"fieldtype": "Data",
			"fieldname": "pdo_category",
		},
		{
			"label": _("COST CENTER "),
			"fieldtype": "Data",
			"fieldname": "cost_center",
		},
	]

	return columns