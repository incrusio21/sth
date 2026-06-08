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
			"label": _("Bulan"),
			"fieldname": "bulan",
			"fieldtype": "Data",
		},
		{
			"label": _("Tanggal"),
			"fieldname": "tanggal",
			"fieldtype": "Date",
		},
		{
			"label": _("Panjang Mtr"),
			"fieldname": "panjang_mtr",
			"fieldtype": "Data",
		},
		{
			"label": _("Lebar Mtr"),
			"fieldname": "lebar_mtr",
			"fieldtype": "Data",
		},
		{
			"label": _("Tinggi Hari Ini Cm"),
			"fieldname": "tinggi_hari_ini_cm",
			"fieldtype": "Data",
		},
		{
			"label": _("Tinggi Hari Ini Mtr"),
			"fieldname": "tinggi_hari_ini_mtr",
			"fieldtype": "Data",
		},
		{
			"label": _("Volume Waduk M³"),
			"fieldname": "volume_waduk_m3",
			"fieldtype": "Data",
		},
	]
 
	return columns

def get_data(filters):
	data = []
 
	data.append({
		"bulan": "Jan"
	})

	return data