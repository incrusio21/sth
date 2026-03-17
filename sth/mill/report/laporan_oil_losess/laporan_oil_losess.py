# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import calendar
from datetime import datetime, date
from calendar import monthrange
from frappe.utils import add_days, days_diff, flt, getdate, get_first_day_of_week, get_last_day_of_week, month_diff, now, rounded

def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data

def get_columns(filters):
	columns = [
		{
			"fieldname": "text",
			"label": _("TANGGAL"),
			"fieldtype": "Data",
			"width": 350,
			"align": "left"
		},
		{
			"fieldname": "percent",
			"label": _(""),
			"fieldtype": "Data",
			"width": 50,
			"align": "left"
		}
	]
	
	bulan = filters.get("bulan")
	tahun = filters.get("tahun")
	
	month_map = {
		"Januari": 1, "Februari": 2, "Maret": 3, "April": 4,
		"Mei": 5, "Juni": 6, "Juli": 7, "Agustus": 8,
		"September": 9, "Oktober": 10, "November": 11, "Desember": 12
	}
	
	month_num = month_map.get(bulan, 1)
	num_days = calendar.monthrange(int(tahun), month_num)[1]
	
	for day in range(1, num_days + 1):
		date_obj = datetime(int(tahun), month_num, day)
		label = str(day)
		
		columns.append({
			"fieldname": f"day_{day}",
			"label": label,
			"fieldtype": "Data",
			"width": 50,
			"align": "center"
		})
  
	return columns

def get_data(filters):
	month_map = {
    "Januari": 1,
    "Februari": 2,
    "Maret": 3,
    "April": 4,
    "Mei": 5,
    "Juni": 6,
    "Juli": 7,
    "Agustus": 8,
    "September": 9,
    "Oktober": 10,
    "November": 11,
    "Desember": 12
	}

	bulan = filters.get("bulan")
	tahun = filters.get("tahun")
	company = filters.get("company")
	unit = filters.get("unit")

	month_num = month_map.get(bulan)

	conditions = ["MONTH(olos.tanggal) = %s", "YEAR(olos.tanggal) = %s"]
	values = [month_num, tahun]

	if company:
		conditions.append("olos.company = %s")
		values.append(company)

	if unit:
		conditions.append("olos.unit = %s")
		values.append(unit)

	query = frappe.db.sql(f"""
		SELECT 
			DAY(olos.tanggal) AS day,
			olos.*,
			mb.*,
			sscdb.*
		FROM `tabOil Losess On Sampel` AS olos
		LEFT JOIN `tabMass Balance` AS mb 
			ON mb.date = olos.tanggal
		LEFT JOIN `tabSounding Stock CPO di BST` AS sscdb
			ON sscdb.tanggal = olos.tanggal
		WHERE {" AND ".join(conditions)}
	""", values, as_dict=1)

	# map data berdasarkan day
	day_map = {int(q["day"]): q for q in query}

	data = []

	# =========================
	# RENDEMEN
	# =========================
	row_rendemen = {
		"rendemen": True,
		"text": "<b>RENDEMEN CPO</b>",
		"percent": "(%)",
	}

	for day, q in day_map.items():
		row_rendemen[f"day_{day}"] = q.get("oer_netto_2", 0)

	data.append(row_rendemen)

	data.append({
		"text": "<b>KEHILANGAN MINYAK DALAM ZAT BASAH</b>"
	})

	# =========================
	# STRUCTURE
	# =========================
	label_row = [
		{
			"parent": "Losses Press / TBS < 0,500 %",
			"child": [
				{"text": "Fibre Press On sample", "field": "fiber_press_"},
				{"text": "Fiber / Nut dalam Press cake", "field": "fibernut_"},
				{"text": "NUT / TBS", "field": "nuttbs"},
			]
		},
		{
			"parent": "Losses Nut / TBS < 0.100 %",
			"child": [
				{"text": "Nut Press on sample", "field": "nut_press_"},
				{"text": "Nut / TBS", "field": "nuttbs"},
			]
		},
		{
			"parent": "Losses fibre Bunch press / TBS < 0.220 %",
			"child": [
				{"text": "Fiber Bunch Press on sample", "field": "fiber_bunch_press_"},
				{"text": "Fiber bunch Press/ TBS", "field": "fiber_bunch_presstbs"},
			]
		},
		{
			"parent": "Losses Heavy Phase Separator / TBS < 0.305 %",
			"child": [
				{"text": "Heavy Phase Separator On sample", "field": "heavy_phase_separator_"},
				{"text": "Lumpur Separator / TBS", "field": "lumpur_separatortbs"},
			]
		},
		{
			"parent": "Losses Sludge Decanter / TBS < 0.340 %",
			"child": [
				{"text": "Heavy Phase Decanter on sample", "field": "heavy_phase_decanter_"},
				{"text": "Sludge Decanter / TBS", "field": "sludge_decantertbs"},
			]
		},
		{
			"parent": "Losses Soild Decanter / TBS < 0.080 %",
			"child": [
				{"text": "Solid Decanter on sample", "field": "solid_decanter_"},
				{"text": "Solid Decanter / TBS", "field": "solid_decantertbs"},
			]
		},
		{
			"parent": "Losses Air Rebusan / TBS < 0.132 %",
			"child": [
				{"text": "Air Rebusan on sample", "field": "air_rebusan_"},
				{"text": "Air Rebusan / TBS", "field": "air_rebusantbs"},
			]
		},
		{
			"parent": "Losses Finall Effluent / TBS < 0,430 %",
			"child": [
				{"text": "Finall Effluent Oil on sample", "field": "finall_effluent_"},
				{"text": "Finall Effluent / TBS", "field": "final_effluenttbs_"},
			]
		},
		{
			"parent": "Losses Minyak di USB / TBS < 0.010 %",
			"child": [
				{"text": "Minyak / Berondolan", "field": "minyakbrondolan"},
				{"text": "Berondolan / USB", "field": "brondolanusb"},
				{"text": "USB on sample", "field": "usb_"},
				{"text": "Empty Bunch / TBS", "field": "empty_bunchtbs"},
			]
		},
		{
			"parent": "Losses Sludge Centrifuge / TBS < 0.340 %",
			"child": [
				{"text": "Heavy Phase Sludge Centrifuge on sample", "field": "heavy_phase_sludge_centrifuge_"},
				{"text": "Sludge Centriguge / TBS", "field": "sludge_centrifugetbs"},
			]
		},
	]

	parent_rows = []

	# =========================
	# LOOP STRUCTURE
	# =========================
	for row in label_row:
		child_rows = []

		for child in row["child"]:
			row_data = {
				"text": child["text"],
				"percent": "(%)"
			}

			for day, q in day_map.items():
				row_data[f"day_{day}"] = q.get(child["field"], 0)

			child_rows.append(row_data)
			data.append(row_data)

		parent_row = {
			"parent": True,
			"text": row["parent"],
			"percent": "(%)"
		}

		for day in day_map:
			value = 1

			for c in child_rows:
				value *= flt(c.get(f"day_{day}", 0))

			parent_row[f"day_{day}"] = value / 100

		data.append(parent_row)
		parent_rows.append(parent_row)

	# =========================
	# TOTAL LOSSES
	# =========================
	row_total_losses = {
		"total": True,
		"text": "<b>Total Losses minyak / TBS <1.300 %</b>",
		"percent": "(%)"
	}

	# =========================
	# EFFICIENCY
	# =========================
	row_efficiency = {
		"text": "<b>Efficiency Extraksi CPO</b>",
		"percent": "(%)"
	}

	for day in day_map:
		field = f"day_{day}"
		total_losses = sum(flt(p.get(field)) for p in parent_rows)
		row_total_losses[field] = total_losses
		rendemen = flt(row_rendemen.get(field))
		if rendemen + total_losses:
			row_efficiency[field] = (rendemen / (rendemen + total_losses)) * 100

	data.extend([
		row_total_losses,
		row_efficiency
	])

	return data
