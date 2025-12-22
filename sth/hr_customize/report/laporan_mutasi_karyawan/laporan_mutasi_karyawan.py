# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []

	query_l_mutasi_karyawan = frappe.db.sql("""
		SELECT
		et.employee_name as nama,
		"Mutasi" as type,
		et.transfer_date as tanggal,
		CASE
			WHEN eph.property = "Company" THEN eph.current
			ELSE null
		END as pt_lama,
		CASE
			WHEN eph.property = "Unit" THEN eph.current
			ELSE null
		END as unit_lama,
		CASE
			WHEN eph.property = "Grade" THEN eph.current
			ELSE null
		END as gol_lama,
		CASE
			WHEN eph.property = "Employment Type" THEN eph.current
			ELSE null
		END as level_lama,
		CASE
			WHEN eph.property = "Company" THEN eph.new
			ELSE null
		END as pt_baru,
		CASE
			WHEN eph.property = "Unit" THEN eph.new
			ELSE null
		END as unit_baru,
		CASE
			WHEN eph.property = "Grade" THEN eph.new
			ELSE null
		END as gol_baru,
		CASE
			WHEN eph.property = "Employment Type" THEN eph.new
			ELSE null
		END as level_baru
		FROM `tabEmployee Transfer` as et
		JOIN `tabEmployee Property History` as eph ON eph.parent = et.name
		JOIN `tabEmployee` as e ON e.name = et.employee
		WHERE eph.property IN ("Company", "Unit", "Grade", "Employment Type") {};
  """.format(conditions), filters, as_dict=True)

	for emp_tranfer in query_l_mutasi_karyawan:
		data.append(emp_tranfer)

	return columns, data

def get_condition(filters):
	conditions = ""

	if filters.get("pt"):
		conditions += " AND et.company = %(pt)s"

	if filters.get("unit"):
		conditions += " AND e.unit = %(unit)s"

	if filters.get("golongan"):
		conditions += " AND e.grade = %(golongan)s"

	if filters.get("level"):
		conditions += " AND e.employment_type = %(level)s"

	if filters.get("nama"):
		conditions += " AND e.name = %(nama)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("Nama"),
			"fieldtype": "Data",
			"fieldname": "nama",
		},
		{
			"label": _("Type"),
			"fieldtype": "Data",
			"fieldname": "type",
		},
		{
			"label": _("Tanggal"),
			"fieldtype": "Date",
			"fieldname": "tanggal",
		},
		{
			"label": _("PT Lama"),
			"fieldtype": "Data",
			"fieldname": "pt_lama",
		},
		{
			"label": _("Unit Lama"),
			"fieldtype": "Data",
			"fieldname": "unit_lama",
		},
		{
			"label": _("Gol Lama"),
			"fieldtype": "Data",
			"fieldname": "gol_lama",
		},
		{
			"label": _("Level Lama"),
			"fieldtype": "Data",
			"fieldname": "level_lama",
		},
		{
			"label": _("PT Baru"),
			"fieldtype": "Data",
			"fieldname": "pt_baru",
		},
		{
			"label": _("Unit Baru"),
			"fieldtype": "Data",
			"fieldname": "unit_baru",
		},
		{
			"label": _("Gol Baru"),
			"fieldtype": "Data",
			"fieldname": "gol_baru",
		},
		{
			"label": _("Level Baru"),
			"fieldtype": "Data",
			"fieldname": "level_baru",
		},
	]

	return columns