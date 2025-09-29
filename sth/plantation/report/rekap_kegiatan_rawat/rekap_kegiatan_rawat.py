# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []

	query_rkr = frappe.db.sql("""
		SELECT 
		bpt.name,
		bpt.kategori_kegiatan,
		k.kd_kgt as kode_kegiatan,
		k.nm_kgt as nama_kegiatan,
		pk.kd_kgt as kode_parent_kegiatan,
		pk.nm_kgt as nama_parent_kegiatan,
		CASE 
				WHEN bpt.kategori_kegiatan  = 'BBT' THEN ROUND(ROUND(SUM(dbup.qty), 2) * ROUND(SUM(dbup.rotasi), 2), 2)
				ELSE ROUND(ROUND(SUM(dbpr.qty), 2) * ROUND(SUM(dbpr.rotasi), 2), 2)
		END AS volume,
		bpt.grand_total as budget
		FROM `tabBudget Perawatan Tahunan` AS bpt
		JOIN `tabKegiatan` as k ON k.name = bpt.kegiatan
		JOIN `tabKegiatan` as pk ON pk.name = k.parent_kegiatan
		LEFT JOIN `tabDetail Budget Upah Pembibitan` AS dbup ON dbup.parent = bpt.name
		LEFT JOIN `tabDetail Budget Upah Perawatan` AS dbpr ON dbpr.parent = bpt.name
		WHERE bpt.company IS NOT NULL {}
		GROUP BY bpt.name;
	""".format(conditions), filters, as_dict=True)

	grouped = {}
	for row in query_rkr:
		key = row['nama_parent_kegiatan']
		if key not in grouped:
			grouped[key] = []
		grouped[key].append(row)
	
	result = []
	for parent, items in grouped.items():
		result.append({
			'nama_parent_kegiatan': parent,
			'items': items
		})
	
	for rkr in result:
		data.append({
			'nama_kegiatan': rkr['nama_parent_kegiatan'],
			'no_kegiatan': rkr['items'][0]['kode_parent_kegiatan']
		})

		for i_rkr in rkr['items']:
			data.append({
				'nama_kegiatan': i_rkr['nama_kegiatan'],
				'no_kegiatan': i_rkr['kode_kegiatan'],
				'volume': i_rkr['volume'],
				'budget': i_rkr['budget'],
				'cost_sat': round(i_rkr['budget'] / i_rkr['volume'], 2)
			})

	data.append({
		'nama_kegiatan': 'TOTAL',
		'volume': round(sum(d.get("volume", 0) for d in data), 2),
		'budget': round(sum(d.get("budget", 0) for d in data), 2),
		'cost_sat': round(sum(d.get("cost_sat", 0) for d in data), 2),
	})

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
			"label": _("NO KEGIATAN"),
			"fieldtype": "Data",
			"fieldname": "no_kegiatan",
		},
		{
			"label": _("NAMA KEGIATAN"),
			"fieldtype": "Data",
			"fieldname": "nama_kegiatan",
			"width": 350
		},
		{
			"label": _("VOLUME"),
			"fieldtype": "Data",
			"fieldname": "volume"
		},
		{
			"label": _("BUDGET"),
			"fieldtype": "Currency",
			"fieldname": "budget",
			"width": 150
		},
		{
			"label": _("COST/SAT"),
			"fieldtype": "Currency",
			"fieldname": "cost_sat",
			"width": 150
		}
	]

	return columns
