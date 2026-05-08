# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []
 
	data.append({
		"periode": "2026"
	})

	return columns, data

def get_condition(filters):
	conditions = ""

	if filters.get("company"):
		conditions += " AND pi.company = %(company)s"

	if filters.get("unit"):
		conditions += " AND pi.unit = %(unit)s"

	if filters.get("from_date") and filters.get("to_date"):
		conditions += " AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("Periode"),
			"fieldtype": "Data",
			"fieldname": "periode",
		},
		{
			"label": _("Kode Barang"),
			"fieldtype": "Data",
			"fieldname": "kode_barang",
		},
		{
			"label": _("Nama Barang"),
			"fieldtype": "Data",
			"fieldname": "nama_barang",
		},
		{
			"label": _("Kelompok Barang"),
			"fieldtype": "Data",
			"fieldname": "kelompok_barang",
		},
		{
			"label": _("Sub Kelompok Barang"),
			"fieldtype": "Data",
			"fieldname": "sub_kelompok_barang",
		},
		{
			"label": _("Tanggal Terakhir PO"),
			"fieldtype": "Date",
			"fieldname": "tanggal_terakhir_po",
		},
		{
			"label": _("Jumlah QTY"),
			"fieldtype": "Data",
			"fieldname": "jumlah_qty",
		},
		{
			"label": _("Jumlah Hari"),
			"fieldtype": "Data",
			"fieldname": "jumlah_hari",
		},
		{
			"label": _("Total"),
			"fieldtype": "Data",
			"fieldname": "total",
		},
	]

	return columns