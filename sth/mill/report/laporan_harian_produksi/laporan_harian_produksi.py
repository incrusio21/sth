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
			"label": _("TBS PROSES & PRODUKSI MS + KS"),
			"fieldname": "tbs_proses_dan_produksi",
			"fieldtype": "Data",
		},
		{
			"label": _("Satuan"),
			"fieldname": "satuan",
			"fieldtype": "Data",
		},
		{
			"label": _("HARI INI Netto (1)"),
			"fieldname": "hari_ini_netto_1",
			"fieldtype": "Float",
		},
		{
			"label": _("HARI INI Netto (1)"),
			"fieldname": "hari_ini_sortasi",
			"fieldtype": "Float",
		},
		{
			"label": _("HARI INI Netto (2)"),
			"fieldname": "hari_ini_netto_2",
			"fieldtype": "Float",
		},
		{
			"label": _("s/d HARI INI Netto (1)"),
			"fieldname": "sd_hari_ini_netto_1",
			"fieldtype": "Float",
		},
		{
			"label": _("s/d HARI INI Netto (1)"),
			"fieldname": "sd_hari_ini_sortasi",
			"fieldtype": "Float",
		},
		{
			"label": _("s/d HARI INI Netto (2)"),
			"fieldname": "sd_hari_ini_netto_2",
			"fieldtype": "Float",
		},
		{
			"label": _("Budget Bulan Ini"),
			"fieldname": "budget_bulan_ini",
			"fieldtype": "Currency",
		},
		{
			"label": _("s/d BULAN INI Netto (1)"),
			"fieldname": "sd_bulan_ini_netto_1",
			"fieldtype": "Float",
		},
		{
			"label": _("s/d BULAN INI Netto (1)"),
			"fieldname": "sd_bulan_ini_sortasi",
			"fieldtype": "Float",
		},
		{
			"label": _("s/d BULAN INI Netto (2)"),
			"fieldname": "sd_bulan_ini_netto_2",
			"fieldtype": "Float",
		},
		{
			"label": _("Budget s/d Bulan Ini"),
			"fieldname": "budget_sd_bulan_ini",
			"fieldtype": "Currency",
		},
		{
			"label": _("Budget Tahun Ini"),
			"fieldname": "budget_tahun_ini",
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
		"tbs_proses_dan_produksi": "2025-05"
	})

	return data