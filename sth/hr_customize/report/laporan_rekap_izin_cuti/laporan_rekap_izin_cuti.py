# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []

	query_l_daftar_izin_cuti = frappe.db.sql("""
		SELECT
		la.company as pt,
		e.unit as unit,
		e.grade as golongan,
		e.employment_type as level,
		la.leave_type as jenis_izin_cuti,
		COUNT(la.employee) as jumlah_orang
		FROM `tabLeave Allocation` as la
		JOIN `tabEmployee` as e ON e.name = la.employee
		GROUP BY la.company, e.unit, e.grade, e.employment_type, la.leave_type;
  """.format(conditions), filters, as_dict=True)

	for leave in query_l_daftar_izin_cuti:
		data.append(leave)

	return columns, data

def get_condition(filters):
	conditions = ""

	if filters.get("jenis_izin_cuti"):
		conditions += " AND la.leave_type = %(jenis_izin_cuti)s"

	if filters.get("pt"):
		conditions += " AND la.company = %(pt)s"

	if filters.get("unit"):
		conditions += " AND e.unit = %(unit)s"

	if filters.get("golongan"):
		conditions += " AND e.grade = %(golongan)s"

	if filters.get("level"):
		conditions += " AND e.employment_type = %(level)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("PT"),
			"fieldtype": "Data",
			"fieldname": "pt",
		},
		{
			"label": _("Unit"),
			"fieldtype": "Data",
			"fieldname": "unit",
		},
		{
			"label": _("Golongan"),
			"fieldtype": "Data",
			"fieldname": "golongan",
		},
		{
			"label": _("Level"),
			"fieldtype": "Data",
			"fieldname": "level",
		},
		{
			"label": _("Jenis Izin Cuti"),
			"fieldtype": "Data",
			"fieldname": "jenis_izin_cuti",
		},
		{
			"label": _("Jumlah Orang"),
			"fieldtype": "Data",
			"fieldname": "jumlah_orang",
		},
	]

	return columns