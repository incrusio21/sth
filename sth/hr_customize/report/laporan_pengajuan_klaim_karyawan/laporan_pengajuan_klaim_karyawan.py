# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []

	query_l_perjalanan_dinas = []

	# for travel in query_l_perjalanan_dinas:
	data.append({
		"pt": "PT. TRIMITRA LESTARI"
	})

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
			"label": _("Jenis"),
			"fieldtype": "Data",
			"fieldname": "jenis",
		},
		{
			"label": _("Tanggal Pengajuan"),
			"fieldtype": "Date",
			"fieldname": "tanggal_pengajuan",
		},
		{
			"label": _("Jumlah Pengajuan"),
			"fieldtype": "Currency",
			"fieldname": "jumlah_pengajuan",
		},
		{
			"label": _("Jumlah Di Setujui"),
			"fieldtype": "Currency",
			"fieldname": "jumlah_di_setujui",
		},
	]

	return columns