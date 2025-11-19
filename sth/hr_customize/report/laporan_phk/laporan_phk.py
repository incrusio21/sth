# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	columns = get_columns(filters)
	data = []

	data.append({
		"nama": "Testing"
	})

	return columns, data


def get_columns(filters):
	columns = [
		{
			"label": _("NAMA"),
			"fieldtype": "Data",
			"fieldname": "nama",
		},
		{
			"label": _("NIK KTP"),
			"fieldtype": "Data",
			"fieldname": "nik_ktp",
		},
		{
			"label": _("NO REK"),
			"fieldtype": "Data",
			"fieldname": "no_rek",
		},
		{
			"label": _("TANGGAL MASUK KERJA"),
			"fieldtype": "Date",
			"fieldname": "tanggal_masuk_kerja",
		},
		{
			"label": _("TANGGAL PHK"),
			"fieldtype": "Date",
			"fieldname": "tanggal_phk",
		},
		{
			"label": _("PT"),
			"fieldtype": "Data",
			"fieldname": "pt",
		},
		{
			"label": _("DASAR PHK"),
			"fieldtype": "Data",
			"fieldname": "dasar_phk",
		},
		{
			"label": _("YANG MENGELUARKAN SURAT"),
			"fieldtype": "Data",
			"fieldname": "yang_mengeluarkan_surat",
		},
		{
			"label": _("PESANGON/KOMPENSASI"),
			"fieldtype": "Currency",
			"fieldname": "pesangon_kompensasi",
		},
		{
			"label": _("PERS 1"),
			"fieldtype": "Data",
			"fieldname": "pers_1",
		},
		{
			"label": _("PERS 2"),
			"fieldtype": "Data",
			"fieldname": "pers_2",
		},
		{
			"label": _("PERS 3"),
			"fieldtype": "Data",
			"fieldname": "pers_3",
		},
		{
			"label": _("PERS 4"),
			"fieldtype": "Data",
			"fieldname": "pers_4",
		},
	]

	return columns