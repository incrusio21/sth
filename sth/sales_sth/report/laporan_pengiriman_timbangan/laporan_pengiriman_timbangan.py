# Copyright (c) 2024, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from datetime import datetime
import calendar
from frappe.utils import flt

def execute(filters=None):
	laporan_type = filters.get("laporan", "Laporan Penerimaan TBS")
	
	if laporan_type == "Rekap Penerimaan TBS":
		columns = get_rekap_columns(filters)
		data = get_rekap_data(filters)
	else:
		columns = get_columns()
		raw_data = get_data(filters)
		data = group_data_by_nama_barang(raw_data, columns)
	
	return columns, data

def group_data_by_nama_barang(data, columns):
	"""Group data by nama_barang: header grup (bold) + semua item + subtotal per grup"""

	SUM_FIELDS = ["bruto", "tara", "netto", "potongan", "berat_normal"]
	all_fieldnames = [c["fieldname"] for c in columns]

	def empty_row():
		row = {}
		for fn in all_fieldnames:
			if fn in SUM_FIELDS:
				row[fn] = None   # numerik -> None supaya tidak jadi 0.00
			else:
				row[fn] = ""     # non-numerik -> string kosong
		return row

	data_sorted = sorted(data, key=lambda r: (r.get("nama_barang") or ""))

	result = []
	current_group = None
	subtotal = {}

	def flush_subtotal():
		if current_group is None:
			return
		row = empty_row()
		row["nama_barang"] = "<b>Total</b>"
		for f in SUM_FIELDS:
			row[f] = subtotal.get(f, 0)   # baris subtotal TETAP diisi angka asli
		result.append(row)

	for row in data_sorted:
		group_name = row.get("nama_barang") or "Tanpa Nama"

		if group_name != current_group:
			flush_subtotal()

			current_group = group_name
			subtotal = {f: 0 for f in SUM_FIELDS}

			header_row = empty_row()   # semua field numerik None -> kosong, bukan 0.00
			header_row["nama_barang"] = f"<b>{group_name}</b>"
			result.append(header_row)

		data_row = dict(row)
		data_row["nama_barang"] = ""
		result.append(data_row)

		for f in SUM_FIELDS:
			subtotal[f] += flt(row.get(f) or 0)

	flush_subtotal()

	return result

def get_columns():
	"""Define kolom-kolom untuk laporan penerimaan TBS"""
	return [
		{
			"fieldname": "nama_barang",
			"label": _("Nama Barang"),
			"fieldtype": "HTML",
			"width": 120
		},
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
			"fieldname": "docname",
			"label": _("Docname"),
			"fieldtype": "Link",
			"options": "Timbangan",
			"width": 100
		},
		{
			"fieldname": "license_number",
			"label": _("Kode Alat"),
			"fieldtype": "Data",
			"width": 100
		},
		{
			"fieldname": "contract_no",
			"label": _("Nomor Kontrak"),
			"fieldtype": "Data",
			"width": 100
		},
		# {
		# 	"fieldname": "contract_no_2",
		# 	"label": _("Nomor Kontrak 2"),
		# 	"fieldtype": "Data",
		# 	"width": 100
		# },
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
			"fieldtype": "Float",
			"width": 120
		},
		{
			"fieldname": "potongan",
			"label": _("Potongan (kg)"),
			"fieldtype": "Float",
			"width": 120
		},
		{
			"fieldname": "berat_normal",
			"label": _("Berat Normal"),
			"fieldtype": "Float",
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
	
	# data = frappe.db.sql("""
	# 	SELECT
	# 		posting_date,
	# 		weight_in_time,
	# 		weight_out_time,
	# 		supplier,
	# 		ticket_number,
	# 		name as docname,
	# 		license_number,
	# 		do_no as contract_no,
	# 		no_do_2 as contract_no_2,
	# 		bruto,
	# 		tara,
	# 		netto,
	# 		ROUND(potongan_sortasi * netto / 100, 0) as potongan,
	# 		netto - ROUND(netto * (potongan_sortasi / 100), 0) as berat_normal,
	# 		driver_name
	# 	FROM
	# 		`tabTimbangan`
	# 	WHERE
	# 		type = "Dispatch"
	# 		AND docstatus = 1
	# 		{conditions}
	# 	ORDER BY
	# 		posting_date, weight_in_time
	# """.format(conditions=conditions), filters, as_dict=1)

	data = frappe.db.sql("""
		SELECT
			t.nama_barang,
			t.posting_date,
			t.weight_in_time,
			t.weight_out_time,
			t.supplier,
			t.ticket_number,
			t.name as docname,
			t.license_number,
			do1.sales_order as contract_no,
			t.bruto,
			t.tara,
			t.netto,
			ROUND(t.potongan_sortasi * t.netto / 100, 0) as potongan,
			t.netto - ROUND(t.netto * (t.potongan_sortasi / 100), 0) as berat_normal,
			t.driver_name
		FROM
			`tabTimbangan` t
		LEFT JOIN
			`tabDelivery Order` do1 ON do1.name = t.do_no
		WHERE
			t.type = "Dispatch"
			AND t.docstatus = 1
			{conditions}

		UNION ALL

		SELECT
			t.nama_barang,
			t.posting_date,
			t.weight_in_time,
			t.weight_out_time,
			t.supplier,
			t.ticket_number,
			t.name as docname,
			t.license_number,
			do2.sales_order as contract_no,
			t.bruto,
			t.tara,
			t.netto,
			ROUND(t.potongan_sortasi * t.netto / 100, 0) as potongan,
			t.netto - ROUND(t.netto * (t.potongan_sortasi / 100), 0) as berat_normal,
			t.driver_name
		FROM
			`tabTimbangan` t
		LEFT JOIN
			`tabDelivery Order` do2 ON do2.name = t.no_do_2
		WHERE
			t.type = "Dispatch"
			AND t.docstatus = 1
			AND t.no_do_2 IS NOT NULL
			AND t.no_do_2 != ''
			{conditions}

		ORDER BY posting_date, weight_in_time
	""".format(conditions=conditions), filters, as_dict=1)
	
	return data

def get_conditions(filters):
	"""Build kondisi WHERE berdasarkan filter"""
	conditions = []
	
	# if filters.get("tbs"):
	# 	if filters.get("tbs") == "External":
	# 		conditions.append("AND receive_type = 'TBS Eksternal'")
	# 	elif filters.get("tbs") == "Internal":
	# 		conditions.append("AND receive_type = 'TBS Internal'")
	
	if filters.get("supplier"):
		conditions.append("AND t.supplier = %(supplier)s")
	
	if filters.get("tanggal_dari"):
		conditions.append("AND t.posting_date >= %(tanggal_dari)s")
	
	if filters.get("tanggal_sampai"):
		conditions.append("AND t.posting_date <= %(tanggal_sampai)s")

	if filters.get("company"):
		conditions.append("AND t.company = %(company)s")

	if filters.get("unit"):
		conditions.append("AND t.unit = %(unit)s")
	
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