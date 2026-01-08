# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []

	query_l_pengajuan_klaim_karyawan = frappe.db.sql("""
		SELECT
		e.company as pt,
		e.grade as gol,
		d.designation_name as jabatan,
		e.employee_name as nama_karyawan,
		ec.name as no_transaksi,
		ec.posting_date as tanggal_pengajuan,
		ec.total_sanctioned_amount as jumlah_pengajuan,
		ec.total_claimed_amount as jumlah_di_setujui
		FROM `tabExpense Claim` as ec
		JOIN `tabEmployee` as e ON e.name = ec.employee
		JOIN `tabDesignation` as d ON d.name = e.designation
		WHERE e.company IS NOT NULL {};
  """.format(conditions), filters, as_dict=True)

	for claim in query_l_pengajuan_klaim_karyawan:
		data.append(claim)

	return columns, data

def get_condition(filters):
	conditions = ""

	if filters.get("pt"):
		conditions += " AND e.company = %(pt)s"

	if filters.get("unit"):
		conditions += " AND e.unit = %(unit)s"
	
	if filters.get("golongan"):
		conditions += " AND e.grade = %(golongan)s"

	if filters.get("jabatan"):
		conditions += " AND e.designation = %(jabatan)s"

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