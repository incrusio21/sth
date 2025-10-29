# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	columns = get_columns(filters)
	data = []
	conditions = get_condition(filters)

	query_kbt = frappe.db.sql("""
		SELECT
		e.no_ktp as nik,
		e.custom_nip as id_pegawai,
		e.custom_no_bpjs_ketenagakerjaan as kode_tk,
		e.employee_name as nama_lengkap,
		DATE_FORMAT(e.date_of_birth, '%%d-%%m-%%Y') as tgl_lahir,
		e.ctc as upah
		FROM `tabEmployee` as e
		WHERE e.relieving_date IS NULL {};
	""".format(conditions), filters, as_dict=True)

	for item in query_kbt:
		row = {}
		for key, value in item.items():
			row[key] = value
		data.append(row)

	return columns, data

def get_condition(filters):
	conditions = "AND e.company = %(company)s"

	if filters.get("employee_grade"):
		conditions += " AND e.grade = %(employee_grade)s"
	
	if filters.get("employment_type"):
		conditions += " AND e.employment_type = %(employment_type)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("NIK"),
			"fieldtype": "Data",
			"fieldname": "nik",
		},
		{
			"label": _("ID_PEGAWAI"),
			"fieldtype": "Data",
			"fieldname": "id_pegawai",
		},
		{
			"label": _("KODE_TK"),
			"fieldtype": "Data",
			"fieldname": "kode_tk",
		},
		{
			"label": _("NAMA_LENGKAP"),
			"fieldtype": "Data",
			"fieldname": "nama_lengkap",
		},
		{
			"label": _("TGL_LAHIR"),
			"fieldtype": "Data",
			"fieldname": "tgl_lahir",
		},
		{
			"label": _("UPAH"),
			"fieldtype": "Data",
			"fieldname": "upah",
		},
		{
			"label": _("RAPEL"),
			"fieldtype": "Data",
			"fieldname": "rapel",
		},
		{
			"label": _("BLTH"),
			"fieldtype": "Data",
			"fieldname": "blth",
		},
		{
			"label": _("NPP"),
			"fieldtype": "Data",
			"fieldname": "npp",
		},
	]

	return columns