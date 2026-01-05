# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []

	query_l_daftar_karyawan = frappe.db.sql("""
		SELECT
			e.company AS pt,
			e.unit AS unit,
			e.grade AS golongan,
			e.employment_type AS status_level,

			SUM(
				CASE
					WHEN e.relieving_date IS NULL THEN 1
					ELSE 0
				END
			) AS aktif,

			SUM(
				CASE
					WHEN e.relieving_date IS NOT NULL THEN 1
					ELSE 0
				END
			) AS keluar

		FROM `tabEmployee` e
		WHERE e.company IS NOT NULL {}
		GROUP BY
			e.company,
			e.unit,
			e.grade,
			e.employment_type;
	""".format(conditions), filters, as_dict=True)

	employee = sorted(query_l_daftar_karyawan, key=lambda x: (
    x.get("pt") or "",
    x.get("unit") or "",
    x.get("golongan") or "",
    x.get("status_level") or ""
	))

	last_pt = None
	last_unit = None
	last_golongan = None

	for d in employee:
		row = d.copy()

		# PT
		if d["pt"] == last_pt:
				row["pt"] = ""
		else:
				last_pt = d["pt"]
				last_unit = None
				last_golongan = None

		# Unit
		if d["unit"] == last_unit:
				row["unit"] = ""
		else:
				last_unit = d["unit"]
				last_golongan = None

		# Golongan
		if d["golongan"] == last_golongan:
				row["golongan"] = ""
		else:
				last_golongan = d["golongan"]

		data.append(row)

	data.append({
		"status_level": "Total",
		"aktif": sum(d.get("aktif", 0) for d in data),
		"keluar": sum(d.get("keluar", 0) for d in data),
	})

	return columns, data

def get_condition(filters):
	conditions = ""

	if filters.get("pt"):
		conditions += " AND e.company = %(pt)s"

	if filters.get("unit"):
		conditions += " AND e.unit = %(unit)s"

	if filters.get("golongan"):
		conditions += " AND e.grade = %(golongan)s"

	if filters.get("status_level"):
		conditions += " AND e.employment_type = %(status_level)s"

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
			"label": _("Status/Level"),
			"fieldtype": "Data",
			"fieldname": "status_level",
		},
		{
			"label": _("Aktif (Org)"),
			"fieldtype": "Data",
			"fieldname": "aktif",
		},
		{
			"label": _("Keluar (Org)"),
			"fieldtype": "Data",
			"fieldname": "keluar",
		},
		{
			"label": _("Keterangan"),
			"fieldtype": "Data",
			"fieldname": "keterangan",
		},
	]

	return columns
