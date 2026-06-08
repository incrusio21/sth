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
			"label": _("Periode"),
			"fieldname": "periode",
			"fieldtype": "Data",
		},
		{
			"label": _("Kode Barang"),
			"fieldname": "kode_barang",
			"fieldtype": "Data",
		},
		{
			"label": _("Nama Barang"),
			"fieldname": "nama_barang",
			"fieldtype": "Data",
		},
		{
			"label": _("Satuan"),
			"fieldname": "satuan",
			"fieldtype": "Data",
		},
		{
			"label": _("Kuantitas"),
			"fieldname": "kuantitas",
			"fieldtype": "Float",
		},
		{
			"label": _("Harga Satuan"),
			"fieldname": "harga_satuan",
			"fieldtype": "Currency",
		},
		{
			"label": _("Total Harga"),
			"fieldname": "total_harga",
			"fieldtype": "Currency",
		},
	]
 
	return columns

def get_data(filters):
	data = []
 
	data.append({
		"periode": "2025-05"
	})

	return data