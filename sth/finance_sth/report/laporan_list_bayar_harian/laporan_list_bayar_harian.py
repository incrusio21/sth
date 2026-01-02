# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []

	data.append({
		"jenis_transaksi": "PEMBELIAN TBS LUAR"
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
			"label": _("JENIS TRANSAKSI"),
			"fieldtype": "Data",
			"fieldname": "jenis_transaksi",
		},
		{
			"label": _("PT"),
			"fieldtype": "Data",
			"fieldname": "pt",
		},
		{
			"label": _("URAIAN - VENDOR - PT UNIT"),
			"fieldtype": "Data",
			"fieldname": "uraian_vendor_unit",
		},
		{
			"label": _("NO. PAYMENT VOUCHER"),
			"fieldtype": "Data",
			"fieldname": "no_pay_voucher",
		},
		{
			"label": _("NO REFF MCM"),
			"fieldtype": "Data",
			"fieldname": "no_reff_mcm",
		},
		{
			"label": _("*PAYMENT SCHEDULE*"),
			"fieldtype": "Data",
			"fieldname": "payment_schedule",
		},
		{
			"label": _("*PAYMENT STATUS*"),
			"fieldtype": "Data",
			"fieldname": "payment_status",
		},
	]

	return columns