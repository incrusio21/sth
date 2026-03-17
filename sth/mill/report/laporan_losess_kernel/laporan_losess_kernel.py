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

	conditions = ["MONTH(klos.tanggal) = %s", "YEAR(klos.tanggal) = %s"]
	values = [month_num, tahun]

	if company:
		conditions.append("klos.company = %s")
		values.append(company)

	if unit:
		conditions.append("klos.unit = %s")
		values.append(unit)

	query = frappe.db.sql(f"""
		SELECT 
			DAY(klos.tanggal) AS day,
			klos.*,
			mb.*,
			sscdb.*
		FROM `tabKernel Losess on Sampel` AS klos
		LEFT JOIN `tabMass Balance` AS mb 
			ON mb.date = klos.tanggal
		LEFT JOIN `tabSounding Stock CPO di BST` AS sscdb
			ON sscdb.tanggal = klos.tanggal
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
		"text": "<b>RENDEMEN KERNEL</b>",
		"percent": "(%)",
	}

	for day, q in day_map.items():
		row_rendemen[f"day_{day}"] = q.get("oer_netto_2", 0)

	data.append(row_rendemen)

	data.append({
		"text": "<b>DATA KEHILANGAN KERNEL</b>"
	})

	# =========================
	# STRUCTURE
	# =========================
	label_row = [
		{
			"parent": "Losses Fiber Cyclone/TBS < 0.220 %",
			"child": [
				{"text": "Fibre Cyclone on sample", "field": "fibre_cyclone_"},
				{"text": "Dry matter Fibre / Fibre Press", "field": "dry_matter_fiberfiber_press_"},
				{"text": "Fibre / Nut", "field": "fibernut_"},
				{"text": "NUT / TBS", "field": "nuttbs"},
			]
		},
		{
			"parent": "Losses LTDS 1 / TBS < 0.08 %",
			"child": [
				{"text": "LTDS I on sample", "field": "ltds_1_"},
				{"text": "LTDS 1 / nut", "field": "ltds_1nut"},
				{"text": "NUT / TBS", "field": "nuttbs"},
			]
		},
		{
			"parent": "Losses LTDS II / TBS < 0.02 %",
			"child": [
				{"text": "LTDS II on sample", "field": "ltds_2_"},
				{"text": "LTDS II / nut", "field": "ltds_2nut"},
				{"text": "NUT / TBS", "field": "nuttbs"},
			]
		},
		{
			"parent": "Losses Wet shell / TBS < 0.05 %",
			"child": [
				{"text": "Wet Shell On Sample", "field": "wet_shell_"},
				{"text": "Wet shell / nut", "field": "wet_shellnut"},
				{"text": "NUT / TBS", "field": "nuttbs"},
			]
		},
		{
			"parent": "Losse USB / TBS < 0.010 %",
			"child": [
				{"text": "Empty Bunch / TBS", "field": "empty_bunchtbs"},
				{"text": "Berondolan / USB", "field": "brondolanusb"},
				{"text": "Kernel /Brondolan", "field": "kernelbrondolan_"},
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
		"text": "<b>Total losses kernel / TBS < 0.380 %</b>",
		"percent": "(%)"
	}

	# =========================
	# EFFICIENCY
	# =========================
	row_efficiency = {
		"text": "<b>Effisiensi Extraksi Kernel</b>",
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
