# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []

	q_laporan_thr = frappe.db.sql("""
		SELECT
		tt.company as pt,
		tt.unit as unit,
		DATE_FORMAT(tt.posting_date, '%%Y') as tahun,
		COUNT(CASE WHEN dtt.employment_type = 'KHT' THEN 1 END) AS kht,
		COUNT(CASE WHEN dtt.employment_type = 'PKWT' THEN 1 END) AS pkwt,
		COUNT(CASE WHEN dtt.employment_type = 'KHL' THEN 1 END) AS khl,
		COUNT(CASE WHEN dtt.employment_type IN ('KHT','PKWT','KHL') THEN 1 END) AS total,
		SUM(
				CASE 
						WHEN dtt.employment_type IN ('KHT','PKWT','KHL') 
						THEN dtt.subtotal 
						ELSE 0 
				END
		) AS rupiah
		FROM `tabTransaksi THR` as tt
		JOIN `tabDetail Transaksi THR` as dtt ON dtt.parent = tt.name
		WHERE tt.company IS NOT NULL {}
		GROUP BY tt.company, tt.unit, DATE_FORMAT(tt.posting_date, '%%Y');
  """.format(conditions), filters, as_dict=True)
 
	for thr in q_laporan_thr:
		data.append(thr)

	return columns, data

def get_condition(filters):
	conditions = ""

	if filters.get("pt"):
		conditions += " AND tt.company = %(pt)s"

	if filters.get("unit"):
		conditions += " AND tt.unit = %(unit)s"

	if filters.get("thr"):
		conditions += " AND tt.religion_group = %(thr)s"

	if filters.get("tahun"):
		conditions += " AND DATE_FORMAT(tt.posting_date, '%%Y') = %(tahun)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("PT"),
			"fieldtype": "Data",
			"fieldname": "pt",
		},
		{
			"label": _("Unit"),
			"fieldtype": "Data",
			"fieldname": "unit",
		},
		{
			"label": _("Tahun"),
			"fieldtype": "Data",
			"fieldname": "tahun",
		},
		{
			"label": _("KHT"),
			"fieldtype": "Data",
			"fieldname": "kht",
		},
		{
			"label": _("PKWT"),
			"fieldtype": "Data",
			"fieldname": "pkwt",
		},
		{
			"label": _("KHL"),
			"fieldtype": "Data",
			"fieldname": "khl",
		},
		{
			"label": _("Total"),
			"fieldtype": "Data",
			"fieldname": "total",
		},
		{
			"label": _("Rupiah"),
			"fieldtype": "Currency",
			"fieldname": "rupiah",
		},
	]

	return columns