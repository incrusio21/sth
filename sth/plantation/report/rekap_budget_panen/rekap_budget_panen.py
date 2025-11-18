# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import calendar

def execute(filters=None):
	columns = get_columns(filters)
	data = []
	conditions = get_condition(filters)
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

	query_rbp = frappe.db.sql("""
		SELECT
		bpt.name as doc_name,
		bpt.divisi,
		b.name as blok,
		b.tahun_tanam,
		dbt.luas_areal as luas,
		b.jumlah_pokok as pokok,
		b.sph,
		dbt.amount as kg,
		ROUND(dbt.rp_januari, 2) as jan,
		ROUND(dbt.rp_februari, 2) as feb,
		ROUND(dbt.rp_maret, 2) as mar,
		ROUND(dbt.rp_april, 2) as apr,
		ROUND(dbt.rp_mei, 2) as may,
		ROUND(dbt.rp_juni, 2) as jun,
		ROUND(dbt.rp_juli, 2) as jul,
		ROUND(dbt.rp_agustus, 2) as aug,
		ROUND(dbt.rp_september, 2) as sep,
		ROUND(dbt.rp_oktober, 2) as oct,
		ROUND(dbt.rp_november, 2) as nov,
		ROUND(dbt.rp_desember, 2) as `dec`
		FROM `tabBudget Panen Tahunan` as bpt
		JOIN `tabDetail Budget Tonase` as dbt ON dbt.parent = bpt.name
		LEFT JOIN `tabBlok` as b ON b.name = dbt.item
		WHERE bpt.company IS NOT NULL {}
	""".format(conditions), filters, as_dict=True)

	grouped = []

	for d in query_rbp:
		doc = d['doc_name']
		found = False
		for r in grouped:
			if r['doc_name'] == doc:
				r['items'].append(d)
				found = True
				break
		
		if not found:
			grouped.append({
				'doc_name': doc,
				'items': [d]
			})

	for rbp in grouped:
		sub_total_total = 0
		for item in rbp['items']:
			rbp_total = 0
			rbp_data = {
				"divisi": item['divisi'],
				"blok": item['blok'],
				"tahun_tanam": item['tahun_tanam'],
				"luas": item['luas'],
				"pokok": item['pokok'],
				"sph": item['sph'],
				"kg": round(item['kg'], 0),
			}

			for key, month_field in all_months.items():
				rbp_total += item[key]
				rbp_data[key] = round(item[key], 0)

			rbp_data['total'] = round(rbp_total, 0)

			data.append(rbp_data)
			rbp_total = 0
	
		sub_total_data = {
			"blok": "SUB TOTAL",
			"luas": round(sum(int(d.get("luas", 0)) for d in rbp['items']), 0),
			"pokok": round(sum(int(d.get("pokok", 0)) for d in rbp['items']), 0),
			"sph": round(sum(int(d.get("sph", 0)) for d in rbp['items']), 0),
			"kg": round(sum(int(d.get("kg", 0)) for d in rbp['items']), 0),
		}

		for key, month_field in all_months.items():
			sub_total_total += round(sum(int(d.get(key, 0)) for d in rbp['items']), 0)
			sub_total_data[key] = round(sum(int(d.get(key, 0)) for d in rbp['items']), 0)

		sub_total_data['total'] = round(sub_total_total, 0)

		data.append(sub_total_data)
		sub_total_total = 0

	total_data = {
		"blok": "TOTAL",
		"luas": round(sum(d.get("luas", 0) for d in data if d.get("blok") == "SUB TOTAL"), 0),
		"pokok": round(sum(d.get("pokok", 0) for d in data if d.get("blok") == "SUB TOTAL"), 0),
		"sph": round(sum(d.get("sph", 0) for d in data if d.get("blok") == "SUB TOTAL"), 0),
		"kg": round(sum(d.get("kg", 0) for d in data if d.get("blok") == "SUB TOTAL"), 0),
		"total": round(sum(d.get("total", 0) for d in data if d.get("blok") == "SUB TOTAL"), 0)
	}

	for key, month_field in all_months.items():
		total_data[key] = round(sum(d.get(key, 0) for d in data if d.get("blok") == "SUB TOTAL"), 0)

	data.append(total_data)

	return columns, data

def get_condition(filters):
	conditions = "AND bpt.company = %(company)s"

	if filters.get("unit"):
		conditions += " AND bpt.unit = %(unit)s"
	
	if filters.get("divisi"):
		conditions += " AND bpt.divisi = %(divisi)s"
	
	if filters.get("periode"):
		conditions += " AND bpt.fiscal_year = %(periode)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("DIVISI"),
			"fieldtype": "Data",
			"fieldname": "divisi",
			"width": 150
		},
		{
			"label": _("BLOK"),
			"fieldtype": "Data",
			"fieldname": "blok",
			"width": 150
		},
		{
			"label": _("TAHUN TANAM"),
			"fieldtype": "Data",
			"fieldname": "tahun_tanam",
			"width": 100
		},
		{
			"label": _("LUAS"),
			"fieldtype": "Data",
			"fieldname": "luas",
			"width": 150
		},
		{
			"label": _("POKOK"),
			"fieldtype": "Data",
			"fieldname": "pokok",
			"width": 150
		},
		{
			"label": _("SPH"),
			"fieldtype": "Data",
			"fieldname": "sph",
			"width": 150
		},
		{
			"label": _("KG"),
			"fieldtype": "Data",
			"fieldname": "kg",
			"width": 150
		}
	]

	return columns