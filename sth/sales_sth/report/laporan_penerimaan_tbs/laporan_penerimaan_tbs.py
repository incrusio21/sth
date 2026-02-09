# Copyright (c) 2024, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from datetime import datetime
import calendar

def execute(filters=None):
	laporan_type = filters.get("laporan", "Laporan Penerimaan TBS")
	
	if laporan_type == "Rekap Penerimaan TBS":
		columns = get_rekap_columns(filters)
		data = get_rekap_data(filters)
	else:
		columns = get_columns()
		data = get_data(filters)
	
	return columns, data

def get_columns():
	"""Define kolom-kolom untuk laporan penerimaan TBS"""
	return [
		{
			"fieldname": "posting_date",
			"label": _("Tanggal"),
			"fieldtype": "Date",
			"width": 100
		},
		{
			"fieldname": "weight_in_time",
			"label": _("Jam Masuk"),
			"fieldtype": "Time",
			"width": 100
		},
		{
			"fieldname": "weight_out_time",
			"label": _("Jam Keluar"),
			"fieldtype": "Time",
			"width": 100
		},
		{
			"fieldname": "supplier",
			"label": _("Nama Supplier"),
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 150
		},
		{
			"fieldname": "ticket_number",
			"label": _("Tiket No"),
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "license_number",
			"label": _("Kode Alat"),
			"fieldtype": "Data",
			"width": 100
		},
		{
			"fieldname": "bruto",
			"label": _("Berat Masuk"),
			"fieldtype": "Float",
			"width": 120
		},
		{
			"fieldname": "tara",
			"label": _("Berat Keluar"),
			"fieldtype": "Float",
			"width": 120
		},
		{
			"fieldname": "netto",
			"label": _("Berat Bersih"),
			"fieldtype": "Int",
			"width": 120
		},
		{
			"fieldname": "potongan",
			"label": _("Potongan (kg)"),
			"fieldtype": "Int",
			"width": 120
		},
		{
			"fieldname": "berat_normal",
			"label": _("Berat Normal"),
			"fieldtype": "Int",
			"width": 120
		},
		{
			"fieldname": "driver_name",
			"label": _("Nama Sopir"),
			"fieldtype": "Data",
			"width": 150
		}
	]

def get_data(filters):
	"""Ambil data dari doctype Timbangan berdasarkan filter"""
	
	conditions = get_conditions(filters)
	
	data = frappe.db.sql("""
		SELECT
			posting_date,
			weight_in_time,
			weight_out_time,
			supplier,
			ticket_number,
			license_number,
			bruto,
			tara,
			netto,
			potongan_sortasi * netto / 100 as potongan,
			netto - (potongan_sortasi * netto / 100) as berat_normal,
			driver_name
		FROM
			`tabTimbangan`
		WHERE
			receive_type IN ('TBS Internal', 'TBS Eksternal')
			AND docstatus = 1
			{conditions}
		ORDER BY
			posting_date, weight_in_time
	""".format(conditions=conditions), filters, as_dict=1)
	
	return data

def get_conditions(filters):
	"""Build kondisi WHERE berdasarkan filter"""
	conditions = []
	
	if filters.get("tbs"):
		if filters.get("tbs") == "External":
			conditions.append("AND receive_type = 'TBS Eksternal'")
		elif filters.get("tbs") == "Internal":
			conditions.append("AND receive_type = 'TBS Internal'")
	
	if filters.get("supplier"):
		conditions.append("AND supplier = %(supplier)s")
	
	if filters.get("tanggal_dari"):
		conditions.append("AND posting_date >= %(tanggal_dari)s")
	
	if filters.get("tanggal_sampai"):
		conditions.append("AND posting_date <= %(tanggal_sampai)s")

	if filters.get("company"):
		conditions.append("AND company = %(company)s")

	if filters.get("unit"):
		conditions.append("AND unit = %(unit)s")
	
	return " ".join(conditions)

def get_rekap_columns(filters):
	"""Generate dynamic columns for Rekap report based on the selected month"""
	tanggal = filters.get("tanggal")
	
	if not tanggal:
		tanggal = datetime.today().date()
	elif isinstance(tanggal, str):
		tanggal = datetime.strptime(tanggal, "%Y-%m-%d").date()
	
	year = tanggal.year
	month = tanggal.month
	
	# Get number of days in the month
	days_in_month = calendar.monthrange(year, month)[1]
	
	columns = [
		{
			"fieldname": "driver_name",
			"label": _("Tanggal"),
			"fieldtype": "Data",
			"width": 150
		}
	]
	
	# Add columns for each day
	for day in range(1, days_in_month + 1):
		columns.append({
			"fieldname": f"day_{day}",
			"label": str(day),
			"fieldtype": "Float",
			"width": 100,
			"align": "left"
		})
	
	# Add Total column
	columns.append({
		"fieldname": "total",
		"label": _("Total"),
		"fieldtype": "Float",
		"width": 120
	})
	
	return columns

def get_rekap_data(filters):
	"""Get recap data grouped by driver and date"""
	tanggal = filters.get("tanggal")
	
	if not tanggal:
		tanggal = datetime.today().date()
	elif isinstance(tanggal, str):
		tanggal = datetime.strptime(tanggal, "%Y-%m-%d").date()
	
	year = tanggal.year
	month = tanggal.month
	
	# Get first and last day of the month
	first_day = datetime(year, month, 1).date()
	last_day = datetime(year, month, calendar.monthrange(year, month)[1]).date()
	
	# Query data for Internal TBS
	internal_data = frappe.db.sql("""
		SELECT
			driver_name,
			DAY(posting_date) as day,
			SUM(netto) as total_netto
		FROM
			`tabTimbangan`
		WHERE
			receive_type = 'TBS Internal'
			AND docstatus = 1
			AND posting_date BETWEEN %s AND %s
		GROUP BY
			driver_name, DAY(posting_date)
		ORDER BY
			driver_name, DAY(posting_date)
	""", (first_day, last_day), as_dict=1)
	
	# Query data for External TBS
	external_data = frappe.db.sql("""
		SELECT
			driver_name,
			DAY(posting_date) as day,
			SUM(netto) as total_netto
		FROM
			`tabTimbangan`
		WHERE
			receive_type = 'TBS Eksternal'
			AND docstatus = 1 
			AND posting_date BETWEEN %s AND %s
		GROUP BY
			driver_name, DAY(posting_date)
		ORDER BY
			driver_name, DAY(posting_date)
	""", (first_day, last_day), as_dict=1)
	
	# Process data
	result = []
	
	# Process Internal data
	internal_drivers = process_driver_data(internal_data)
	result.extend(internal_drivers)
	
	# Add Total Internal row
	if internal_drivers:
		total_internal = calculate_total_row(internal_drivers, "Total Internal")
		result.append(total_internal)
	
	# Process External data
	external_drivers = process_driver_data(external_data)
	result.extend(external_drivers)
	
	# Add Total External row
	if external_drivers:
		total_external = calculate_total_row(external_drivers, "Total External")
		result.append(total_external)
	
	return result

def process_driver_data(data):
	"""Process raw data into driver-based rows"""
	drivers = {}
	
	for row in data:
		driver = row.get("driver_name") or "Unknown"
		day = row.get("day")
		netto = row.get("total_netto", 0)
		
		if driver not in drivers:
			drivers[driver] = {"driver_name": driver, "total": 0}
		
		drivers[driver][f"day_{day}"] = netto
		drivers[driver]["total"] += netto
	
	return list(drivers.values())

def calculate_total_row(driver_rows, label):
	"""Calculate total row from driver rows"""
	total_row = {"driver_name": label, "total": 0}
	
	for driver in driver_rows:
		for key, value in driver.items():
			if key.startswith("day_"):
				if key not in total_row:
					total_row[key] = 0
				total_row[key] += value
			elif key == "total":
				total_row["total"] += value
	
	return total_row