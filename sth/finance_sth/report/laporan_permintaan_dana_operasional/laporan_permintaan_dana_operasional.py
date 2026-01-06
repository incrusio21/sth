# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []

	data.append({
		"expenses": "TUNJANGAN PEMBANTU"
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
			"label": _("EXPENSES"),
			"fieldtype": "Data",
			"fieldname": "expenses",
		},
		{
			"label": _("KETERANGAN"),
			"fieldtype": "Data",
			"fieldname": "keterangan",
		},
	]

	return columns