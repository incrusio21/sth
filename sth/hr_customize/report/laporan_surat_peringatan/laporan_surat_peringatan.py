# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import formatdate

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []

	query_l_surat_peringatan = frappe.db.sql("""
		SELECT
		e.unit as unit,
		eg.grievance_type as jenis_sp,
		e.grade as gol_karyawan,
		e.employee_name as nama_karyawan,
		e.date_of_joining as tmk,
		eg.custom_effective_date_from as effective_date_from,
		eg.custom_effective_date_till as effective_date_until
		FROM `tabEmployee Grievance` as eg
		JOIN `tabEmployee` as e ON e.name = eg.raised_by
		WHERE eg.raised_by IS NOT NULL {};
  """.format(conditions), filters, as_dict=True)

	for grievance in query_l_surat_peringatan:
		data.append({
			"unit": grievance.unit,
			"jenis_sp": grievance.jenis_sp,
			"gol_karyawan": grievance.gol_karyawan,
			"nama_karyawan": grievance.nama_karyawan,
			"tmk": grievance.tmk,
			"periode": f"{formatdate(grievance.effective_date_from, 'd MMMM yyyy')} s/d {formatdate(grievance.effective_date_until, 'd MMMM yyyy')}",
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
			"label": _("Unit"),
			"fieldtype": "Data",
			"fieldname": "unit",
		},
		{
			"label": _("Jenis SP"),
			"fieldtype": "Data",
			"fieldname": "jenis_sp",
		},
		{
			"label": _("Gol Karyawan"),
			"fieldtype": "Data",
			"fieldname": "gol_karyawan",
		},
		{
			"label": _("Nama Karyawan"),
			"fieldtype": "Data",
			"fieldname": "nama_karyawan",
		},
		{
			"label": _("TMK"),
			"fieldtype": "Date",
			"fieldname": "tmk",
		},
		{
			"label": _("Periode Masa Berlaku Surat Teguran / Surat Peringatan"),
			"fieldtype": "Data",
			"fieldname": "periode",
		},
	]

	return columns