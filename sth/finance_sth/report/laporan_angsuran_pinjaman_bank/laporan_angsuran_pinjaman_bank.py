# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []

	data.append({
		"customer": "Agrindo Panca Tunggal  PT"
	})

	return columns, data

def get_condition(filters):
	conditions = ""

	if filters.get("bulan"):
		conditions += " AND DATE_FORMAT(dit.posting_date, '%%b') = %(bulan)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("CUSTOMER"),
			"fieldtype": "Data",
			"fieldname": "customer",
		},
		{
			"label": _("No.Pinjaman"),
			"fieldtype": "Data",
			"fieldname": "no_pinjaman",
		},
		{
			"label": _("FAS"),
			"fieldtype": "Data",
			"fieldname": "fas",
		},
		{
			"label": _("Ccy"),
			"fieldtype": "Data",
			"fieldname": "ccy",
		},
		{
			"label": _("Outstanding"),
			"fieldtype": "Currency",
			"fieldname": "outstanding",
		},
		{
			"label": _("From"),
			"fieldtype": "Date",
			"fieldname": "from_date",
		},
		{
			"label": _("Days"),
			"fieldtype": "Data",
			"fieldname": "days",
		},
		{
			"label": _("To /Tgl Pembayaran"),
			"fieldtype": "Date",
			"fieldname": "to_date",
		},
		{
			"label": _("IR"),
			"fieldtype": "Data",
			"fieldname": "ir",
		},
		{
			"label": _("Pokok"),
			"fieldtype": "Currency",
			"fieldname": "pokok",
		},
		{
			"label": _("Bunga"),
			"fieldtype": "Currency",
			"fieldname": "bunga",
		},
		{
			"label": _("Total Kewajiban"),
			"fieldtype": "Currency",
			"fieldname": "total_kewajiban",
		},
	]

	return columns