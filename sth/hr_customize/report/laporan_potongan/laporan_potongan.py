# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []

	query_l_potongan = frappe.db.sql("""
		SELECT
		epd.employee as `id`,
		epd.employee_name as nama,
		epd.rate as jumlah_potongan,
		ep.persetujuan_1 as persetujuan_1,
		ep.persetujuan_2 as persetujuan_2
		FROM `tabEmployee Potongan` as ep
		JOIN `tabEmployee Potongan Details` as epd ON epd.parent = ep.name
		JOIN `tabEmployee` as e ON e.name = epd.employee
		WHERE ep.name IS NOT NULL {};
  """.format(conditions), filters, as_dict=True)

	for potongan in query_l_potongan:
		data.append(potongan)

	return columns, data

def get_condition(filters):
	conditions = ""

	if filters.get("no_transaksi"):
		conditions += " AND ep.name = %(no_transaksi)s"

	if filters.get("tahun"):
		conditions += " AND DATE_FORMAT(ep.posting_date, '%%Y') = %(tahun)s"

	if filters.get("pt"):
		conditions += " AND ep.company = %(pt)s"

	if filters.get("unit"):
		conditions += " AND e.unit = %(unit)s"

	if filters.get("golongan"):
		conditions += " AND e.grade = %(golongan)s"

	if filters.get("potongan"):
		conditions += " AND ep.jenis_potongan = %(potongan)s"

	if filters.get("bulan"):
		conditions += " AND DATE_FORMAT(ep.posting_date, '%%b') = %(bulan)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("ID"),
			"fieldtype": "Data",
			"fieldname": "id",
		},
		{
			"label": _("Nama"),
			"fieldtype": "Data",
			"fieldname": "nama",
		},
		{
			"label": _("Jumlah Potongan"),
			"fieldtype": "Currency",
			"fieldname": "jumlah_potongan",
		},
		{
			"label": _("Persetujuan 1"),
			"fieldty2": "Data",
			"fieldname": "persetujuan_1",
		},
		{
			"label": _("Persetujuan 2"),
			"fieldtype": "Data",
			"fieldname": "persetujuan_2",
		},
	]

	return columns
