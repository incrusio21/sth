# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []

	q_laporan_thr_detail = frappe.db.sql("""
		SELECT 
		e.name as nik,
		dtt.employee_name as nama,
		e.company as pt,
		e.unit as unit,
		tt.posting_date as posting_date,
		e.date_of_joining as tmk,
		dtt.masa_kerja as masa_kerja,
		e.bank_ac_no as no_rek,
		e.bank_name as bank,
		CONCAT(e.grade, '-', e.employment_type) as level_status,
		dtt.subtotal - dtt.uang_daging - dtt.natura as rp,
		dtt.uang_daging as uang_daging,
		dtt.natura as natura,
		(dtt.subtotal - dtt.uang_daging - dtt.natura) + dtt.uang_daging + dtt.natura as jumlah
		FROM `tabDetail Transaksi THR` as dtt
		JOIN `tabEmployee` as e ON e.name = dtt.employee
  	JOIN `tabTransaksi THR` as tt ON tt.name = dtt.parent
   	WHERE tt.company IS NOT NULL {};
  """.format(conditions), filters, as_dict=True)
 
	for thr in q_laporan_thr_detail:
		thr["jumlah_bulan_kerja"] = get_jumlah_bulan_bekerja(thr.get("posting_date"), thr.get("tmk"))
		data.append(thr)

	return columns, data

def get_condition(filters):
	conditions = ""

	if filters.get("pt"):
		conditions += " AND tt.company = %(pt)s"

	if filters.get("unit"):
		conditions += " AND tt.unit = %(unit)s"

	if filters.get("thr"):
		conditions += " AND tt.religion_group = %(thr)s"

	if filters.get("grade"):
		conditions += " AND e.grade = %(grade)s"

	if filters.get("employment_type"):
		conditions += " AND e.employment_type = %(employment_type)s"

	if filters.get("start_periode") and filters.get("end_periode"):
		conditions += " AND tt.posting_date BETWEEN %(start_periode)s AND %(end_periode)s"

	if filters.get("tahun"):
		conditions += " AND DATE_FORMAT(tt.posting_date, '%%Y') = %(tahun)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("NIK"),
			"fieldtype": "Data",
			"fieldname": "nik",
		},
		{
			"label": _("Nama"),
			"fieldtype": "Data",
			"fieldname": "nama",
		},
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
			"label": _("TMK"),
			"fieldtype": "Data",
			"fieldname": "tmk",
		},
		{
			"label": _("Masa Kerja"),
			"fieldtype": "Data",
			"fieldname": "masa_kerja",
		},
		{
			"label": _("No Rek"),
			"fieldtype": "Data",
			"fieldname": "no_rek",
		},
		{
			"label": _("Bank"),
			"fieldtype": "Data",
			"fieldname": "bank",
		},
		{
			"label": _("Jumlah Bulan Kerja"),
			"fieldtype": "Data",
			"fieldname": "jumlah_bulan_kerja",
		},
		{
			"label": _("Level-Status"),
			"fieldtype": "Data",
			"fieldname": "level_status",
		},
		{
			"label": _("THR Rp"),
			"fieldtype": "Currency",
			"fieldname": "rp",
		},
		{
			"label": _("THR Uang Daging"),
			"fieldtype": "Currency",
			"fieldname": "uang_daging",
		},
		{
			"label": _("THR Natura"),
			"fieldtype": "Currency",
			"fieldname": "natura",
		},
		{
			"label": _("THR Jumlah"),
			"fieldtype": "Currency",
			"fieldname": "jumlah",
		},
	]

	return columns

def get_jumlah_bulan_bekerja(posting_date, date_of_joining):
	if not date_of_joining:
		return 0

	today_date = getdate(posting_date)
	doj = getdate(date_of_joining)
	months = (today_date.year - doj.year) * 12 + (today_date.month - doj.month)
	return max(0, months)