# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []

	query_l_ppn_masukan = frappe.db.sql("""
		SELECT 
		si.customer_name as customer,
		si.name as nomor_invoice,
		si.posting_date as tanggal_invoice,
		si.keterangan as keterangan,
		0 as dpp,
		0 as ppn
		FROM `tabSales Invoice` as si
  	WHERE si.company IS NOT NULL {};
  """.format(conditions), filters, as_dict=True)

	for invoice in query_l_ppn_masukan:
		data.append(invoice)

	return columns, data

def get_condition(filters):
	conditions = ""

	if filters.get("company"):
		conditions += " AND si.company = %(company)s"

	if filters.get("unit"):
		conditions += " AND si.unit = %(unit)s"

	if filters.get("from_date") and filters.get("to_date"):
		conditions += " AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("Customer"),
			"fieldtype": "Data",
			"fieldname": "customer",
		},
		{
			"label": _("Nomor invoice"),
			"fieldtype": "Data",
			"fieldname": "nomor_invoice",
		},
		{
			"label": _("Tanggal invoice"),
			"fieldtype": "Date",
			"fieldname": "tanggal_invoice",
		},
		{
			"label": _("Keterangan"),
			"fieldtype": "Data",
			"fieldname": "keterangan",
		},
		{
			"label": _("DPP"),
			"fieldtype": "Currency",
			"fieldname": "dpp",
		},
		{
			"label": _("PPN"),
			"fieldtype": "Currency",
			"fieldname": "ppn",
		},
	]

	return columns
