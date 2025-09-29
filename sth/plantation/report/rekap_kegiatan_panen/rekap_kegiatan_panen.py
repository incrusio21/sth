# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	columns = get_columns(filters)
	data = []
	conditions = get_condition(filters)

	query_rkp = frappe.db.sql("""
	SELECT 
	bpt.tonase_amount as estimasi_produksi,
	bpt.upah_amount as budget_panen,
	bpt.brondolan_amount as budget_kutip_brondolan,
	bpt.peralatan_amount as budget_alat_panen,
	bpt.supervisi_amount as budget_supervisi_panen,
	bpt.langsung_amount as budget_pengangkutan_langsung,
	bpt.tidak_langsung_amount as budget_pengangkutan_tidak_langsung
	FROM `tabBudget Panen Tahunan` as bpt
	WHERE bpt.company IS NOT NULL {}
	LIMIT 1;
	""".format(conditions), filters, as_dict=True)

	# BIAYA PANEN
	data.append({
		'nama_kegiatan': 'BIAYA PANEN'
	})

	# cek data, kalau kosong set default
	if query_rkp and len(query_rkp) > 0:
		row = query_rkp[0]
	else:
		row = {}

	estimasi_produksi = row.get('estimasi_produksi', 0) or 0

	# --- Bagian BIAYA PANEN ---
	kegiatan_list = [
		("PANEN", "budget_panen"),
		("KUTIP BRONDOLAN", "budget_kutip_brondolan"),
		("ALAT PANEN", "budget_alat_panen"),
		("SUPERVISI PANEN", "budget_supervisi_panen"),
	]

	for nama_kegiatan, field in kegiatan_list:
		budget = row.get(field, 0) or 0
		cost_sat = budget / estimasi_produksi if estimasi_produksi else 0

		data.append({
			"nama_kegiatan": nama_kegiatan,
			"budget": round(budget, 2),
			"cost_sat": round(cost_sat, 2)
		})

	data.append({
		"nama_kegiatan": "",
	})

	# PENGANGKUTAN
	data.append({
		'nama_kegiatan': 'PENGANGKUTAN'
	})

	# --- Bagian PENGANGKUTAN ---
	kegiatan_pengangkutan = [
		("PENGANGKUTAN LANGSUNG", "budget_pengangkutan_langsung"),
		("PENGANGKUTAN TIDAK LANGSUNG", "budget_pengangkutan_tidak_langsung"),
	]

	for nama_kegiatan, field in kegiatan_pengangkutan:
		budget = row.get(field, 0) or 0
		cost_sat = budget / estimasi_produksi if estimasi_produksi else 0

		data.append({
			"nama_kegiatan": nama_kegiatan,
			"budget": round(budget, 2),
			"cost_sat": round(cost_sat, 2)
		})

	# TOTAL
	data.append({
		"nama_kegiatan": "TOTAL",
		"budget": round(sum(d.get("budget", 0) for d in data), 2),
		"cost_sat": round(sum(d.get("cost_sat", 0) for d in data), 2)
	})

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
			"label": _("NAMA KEGIATAN"),
			"fieldtype": "Data",
			"fieldname": "nama_kegiatan",
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
