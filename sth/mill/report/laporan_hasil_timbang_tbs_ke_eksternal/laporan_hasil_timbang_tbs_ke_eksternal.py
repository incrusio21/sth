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
			"fieldname": "tanggal_1",
			"fieldtype": "Date",
		},
		{
			"label": _("Tiket No"),
			"fieldname": "ticket_no",
			"fieldtype": "Link",
			"options": "Security Check Point"
		},
		{
			"label": _("Jjg"),
			"fieldname": "jjg",
			"fieldtype": "Data"
		},
		{
			"label": _("Tanggal"),
			"fieldname": "tanggal_2",
			"fieldtype": "Date",
		},
		{
			"label": _("Berat Masuk"),
			"fieldname": "berat_masuk",
			"fieldtype": "Float"
		},
		{
			"label": _("Berat Keluar"),
			"fieldname": "berat_keluar",
			"fieldtype": "Float"
		},
		{
			"label": _("Berat Bersih"),
			"fieldname": "berat_bersih",
			"fieldtype": "Float"
		},
		{
			"label": _("Potongan"),
			"fieldname": "potongan",
			"fieldtype": "Float"
		},
		{
			"label": _("Berat Normal"),
			"fieldname": "berat_normal",
			"fieldtype": "Float"
		},
		{
			"label": _("Berat Pengakuan Jual"),
			"fieldname": "berat_pengakuan_jual",
			"fieldtype": "Float"
		},
		{
			"label": _("Kg"),
			"fieldname": "kg_1",
			"fieldtype": "Float"
		},
		{
			"label": _("%"),
			"fieldname": "percent",
			"fieldtype": "Data"
		},
		{
			"label": _("Transportir"),
			"fieldname": "transportir",
			"fieldtype": "Data",
		},
		{
			"label": _("Kg"),
			"fieldname": "kg_2",
			"fieldtype": "Float",
		},
		{
			"label": _("Harga TBS (Rp/Kg)"),
			"fieldname": "harga_tbs",
			"fieldtype": "Float",
		},
		{
			"label": _("Total Denda (Rp)"),
			"fieldname": "total_denda",
			"fieldtype": "Currency",
		},
		{
			"label": _("Keterangan"),
			"fieldname": "keterangan",
			"fieldtype": "Data",
		},
	]
 
	return columns

def get_data(filters):
	data = []
 
	data.append({
		"tanggal_1": "2025-05"
	})

	return data