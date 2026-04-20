# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []

	data.append({
		"no_transaksi": "ACC-PAY-2026-00082"
	})
 
	return columns, data

def get_condition(filters):
	conditions = ""
	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("No Transaksi"),
			"fieldtype": "Data",
			"fieldname": "no_transaksi",
		},
		{
			"label": _("Tanggal"),
			"fieldtype": "Date",
			"fieldname": "tanggal",
		},
		{
			"label": _("Keterangan"),
			"fieldtype": "Data",
			"fieldname": "keterangan",
		},
		{
			"label": _("Jumlah"),
			"fieldtype": "Currency",
			"fieldname": "jumlah",
		},
	]

	return columns