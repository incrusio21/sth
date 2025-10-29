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
		e.custom_no_bpjs_ketenagakerjaan as kpj,
		e.employee_name as nama_lengkap,
		DATE_FORMAT(e.date_of_birth, '%%d-%%m-%%Y') as tgl_lahir,
		e.custom_sebab_na as sebab_na,
		DATE_FORMAT(e.relieving_date, '%%d-%%m-%%Y') as tgl_kejadian,
		e.reason_for_leaving as keterangan
		FROM `tabEmployee` as e
		WHERE e.relieving_date IS NOT NULL {};
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
	
	if filters.get("from_date") and filters.get("to_date"):
		conditions += " AND e.relieving_date BETWEEN %(from_date)s AND %(to_date)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("KPJ"),
			"fieldtype": "Data",
			"fieldname": "kpj",
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
			"label": _("SEBAB_NA"),
			"fieldtype": "Data",
			"fieldname": "sebab_na",
		},
		{
			"label": _("TGL_KEJADIAN"),
			"fieldtype": "Data",
			"fieldname": "tgl_kejadian",
		},
		{
			"label": _("KETERANGAN"),
			"fieldtype": "Data",
			"fieldname": "keterangan",
		},
	]

	return columns