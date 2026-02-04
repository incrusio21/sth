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
				e.name AS nik,
				e.custom_nip AS id_pegawai,
				e.custom_no_bpjs_ketenagakerjaan AS kode_tk,
				e.employee_name AS nama_lengkap,
				DATE_FORMAT(e.date_of_birth, '%%d-%%m-%%Y') AS tgl_lahir,
				ssa.base AS upah,
				a.amount as rapel,
				a.payroll_date as blth,
				a.npp as npp
		FROM `tabAdditional Salary` a
		JOIN `tabEmployee` e 
				ON e.name = a.employee
		JOIN `tabSalary Structure Assignment` ssa
				ON ssa.employee = a.employee
		JOIN (
				SELECT employee, MAX(from_date) AS max_from_date
				FROM `tabSalary Structure Assignment`
				GROUP BY employee
		) latest_ssa
				ON latest_ssa.employee = ssa.employee
				AND latest_ssa.max_from_date = ssa.from_date
 		WHERE a.company IS NOT NULL {};
	""".format(conditions), filters, as_dict=True)

	for item in query_kbt:
		row = {}
		for key, value in item.items():
			row[key] = value
		data.append(row)

	return columns, data

def get_condition(filters):
	conditions = "AND a.company = %(company)s"

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
			"fieldtype": "Currency",
			"fieldname": "upah",
		},
		{
			"label": _("RAPEL"),
			"fieldtype": "Currency",
			"fieldname": "rapel",
		},
		{
			"label": _("BLTH"),
			"fieldtype": "Date",
			"fieldname": "blth",
		},
		{
			"label": _("NPP"),
			"fieldtype": "Data",
			"fieldname": "npp",
		},
	]

	return columns