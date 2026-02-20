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
		pi.no_fp as nomor_faktur_pajak,
		pi.tanggal_faktur_pajak as tanggal_faktur_pajak,
		pi.supplier as vendor,
		pi.bill_no as nomor_invoice,
		pi.bill_date as tanggal_invoice,
		pi.keterangan as keterangan,
		0 as dpp,
		pi.total_ppn as ppn
		FROM `tabPurchase Invoice` as pi 
  	WHERE pi.company IS NOT NULL {};
  """.format(conditions), filters, as_dict=True)

	for invoice in query_l_ppn_masukan:
		data.append(invoice)

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
			"label": _("Nomor faktur pajak"),
			"fieldtype": "Data",
			"fieldname": "nomor_faktur_pajak",
		},
		{
			"label": _("Tanggal faktur pajak"),
			"fieldtype": "Date",
			"fieldname": "tanggal_faktur_pajak",
		},
		{
			"label": _("Vendor"),
			"fieldtype": "Data",
			"fieldname": "vendor",
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
