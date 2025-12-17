# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []

	query_l_perjalanan_dinas = frappe.db.sql("""
		SELECT
		tr.company as pt,
		e.grade as gol,
		d.designation_name as jabatan,
		e.employee_name as nama_karyawan,
		tr.name as no_transaksi,
		tr.purpose_of_travel as jenis_pjd,
		tr.custom_estimate_depart_date as tanggal_berangkat,
		tr.custom_estimate_arrival_date as tanggal_kembali,
		tr.custom_grand_total_costing as realisasi_biaya
		FROM `tabTravel Request` as tr
		JOIN `tabEmployee` as e ON e.name = tr.employee
		JOIN `tabDesignation` as d ON d.name = e.designation;
  """, as_dict=True)

	for travel in query_l_perjalanan_dinas:
		data.append(travel)

	return columns, data

def get_condition(filters):
	conditions = ""

	if filters.get("from_date") and filters.get("to_date"):
		conditions += " AND eg.date BETWEEN %(from_date)s AND %(to_date)s"

	if filters.get("unit"):
		conditions += " AND e.unit = %(unit)s"

	if filters.get("jenis_sp"):
		conditions += " AND eg.grievance_type = %(jenis_sp)s"

	if filters.get("tipe_karyawan"):
		conditions += " AND e.grade = %(tipe_karyawan)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("PT"),
			"fieldtype": "Data",
			"fieldname": "pt",
		},
		{
			"label": _("Gol"),
			"fieldtype": "Data",
			"fieldname": "gol",
		},
		{
			"label": _("Jabatan"),
			"fieldtype": "Data",
			"fieldname": "jabatan",
		},
		{
			"label": _("Nama Karyawan"),
			"fieldtype": "Data",
			"fieldname": "nama_karyawan",
		},
		{
			"label": _("No Transaksi"),
			"fieldtype": "Data",
			"fieldname": "no_transaksi",
		},
		{
			"label": _("Jenis PJD"),
			"fieldtype": "Data",
			"fieldname": "jenis_pjd",
		},
		{
			"label": _("Tujuan"),
			"fieldtype": "Data",
			"fieldname": "tujuan",
		},
		{
			"label": _("Tanggal Berangkat"),
			"fieldtype": "Date",
			"fieldname": "tanggal_berangkat",
		},
		{
			"label": _("Tanggal Kembali"),
			"fieldtype": "Date",
			"fieldname": "tanggal_kembali",
		},
		{
			"label": _("Kasbon"),
			"fieldtype": "Currency",
			"fieldname": "kasbon",
		},
		{
			"label": _("Realisasi Biaya"),
			"fieldtype": "Currency",
			"fieldname": "realisasi_biaya",
		},
	]

	return columns
