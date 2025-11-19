# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import calendar

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []
	all_months = {
    "jan": "per_januari",
    "feb": "per_februari",
    "mar": "per_maret",
    "apr": "per_april",
    "may": "per_mei",
    "jun": "per_juni",
    "jul": "per_juli",
    "aug": "per_agustus",
    "sep": "per_september",
    "oct": "per_oktober",
    "nov": "per_november",
    "dec": "per_desember"
	}

	# Sub-column bulanan
	for month in range(1, 13):
		columns.append({
			"label": calendar.month_abbr[month].upper(),
			"fieldname": calendar.month_abbr[month].lower(),
			"fieldtype": "Data",
			"width": 150
		})

	columns.append({
		"label": "TOTAL",
		"fieldname": "total",
		"fieldtype": "Data",
		"width": 150
	})

	query_rkm = frappe.db.sql("""
		WITH base AS (
			SELECT
			bpt.name as doc_name,
			i.item_name as nama,
			dbm.uom as satuan,
			dbm.qty as jumlah,
			ROUND(bpt.per_januari, 2) as jan,
			ROUND(bpt.per_februari, 2) as feb,
			ROUND(bpt.per_maret, 2) as mar,
			ROUND(bpt.per_april, 2) as apr,
			ROUND(bpt.per_mei, 2) as may,
			ROUND(bpt.per_juni, 2) as jun,
			ROUND(bpt.per_juli, 2) as jul,
			ROUND(bpt.per_agustus, 2) as aug,
			ROUND(bpt.per_september, 2) as sep,
			ROUND(bpt.per_oktober, 2) as oct,
			ROUND(bpt.per_november, 2) as nov,
			ROUND(bpt.per_desember, 2) as `dec`
			FROM `tabBudget Perawatan Tahunan` as bpt
			JOIN `tabDetail Budget Material` as dbm ON dbm.parent = bpt.name
			JOIN `tabItem` as i ON i.name = dbm.item
			WHERE bpt.company IS NOT NULL {}
		),

		per_doc AS (
			SELECT 
			doc_name,
			nama,
			satuan,
			ROUND(jumlah, 2) as jumlah,
			ROUND(jumlah * (jan/100), 2) as jan,
			ROUND(jumlah * (feb/100), 2) as feb,
			ROUND(jumlah * (mar/100), 2) as mar,
			ROUND(jumlah * (apr/100), 2) as apr,
			ROUND(jumlah * (may/100), 2) as may,
			ROUND(jumlah * (jun/100), 2) as jun,
			ROUND(jumlah * (jul/100), 2) as jul,
			ROUND(jumlah * (aug/100), 2) as aug,
			ROUND(jumlah * (sep/100), 2) as sep,
			ROUND(jumlah * (oct/100), 2) as oct,
			ROUND(jumlah * (nov/100), 2) as nov,
			ROUND(jumlah * (`dec`/100), 2) as `dec`
			FROM base
		)

		SELECT
		nama,
		satuan,
		SUM(jumlah) as jumlah,
		SUM(jan) as jan,
		SUM(feb) as feb,
		SUM(mar) as mar,
		SUM(apr) as apr,
		SUM(may) as may,
		SUM(jun) as jun,
		SUM(jul) as jul,
		SUM(aug) as aug,
		SUM(sep) as sep,
		SUM(oct) as oct,
		SUM(nov) as nov,
		SUM(`dec`) as `dec`
		FROM per_doc
		GROUP BY nama;
	""".format(conditions), filters, as_dict=True)

	for rkm in query_rkm:
		total = 0
		row_data = {
			"nama": rkm['nama'],
			"satuan": rkm['satuan']
		}

		for key, month_field in all_months.items():
			total += rkm[key]
			row_data[key] = round(rkm[key], 0)

		row_data['total'] = round(total, 0)

		data.append(row_data)
		total = 0

	return columns, data

def get_condition(filters):
	conditions = "AND bpt.company = %(company)s"

	if filters.get("unit"):
		conditions += " AND bpt.unit = %(unit)s"
	
	if filters.get("divisi"):
		conditions += " AND bpt.divisi = %(divisi)s"
	
	if filters.get("kegiatan"):
		conditions += " AND bpt.kegiatan = %(kegiatan)s"
	
	if filters.get("periode"):
		conditions += " AND bpt.thn_bgt = %(periode)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("NAMA"),
			"fieldtype": "Data",
			"fieldname": "nama",
			"width": 250
		},
		{
			"label": _("SATUAN"),
			"fieldtype": "Data",
			"fieldname": "satuan",
			"width": 150
		}
	]

	return columns