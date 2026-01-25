# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

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
		e.date_of_joining as tmk,
		dtt.masa_kerja as masa_kerja,
		e.bank_ac_no as no_rek,
		e.bank_name as bank,
		CONCAT(e.grade, '-', e.employment_type) as level_status,
		dtt.subtotal - dtt.uang_daging as rp,
		dtt.uang_daging as uang_daging,
		(dtt.subtotal - dtt.uang_daging) + dtt.uang_daging as jumlah
		FROM `tabDetail Transaksi THR` as dtt
		JOIN `tabEmployee` as e ON e.name = dtt.employee
  	JOIN `tabTransaksi THR` as tt ON tt.name = dtt.parent
   	WHERE tt.company IS NOT NULL {};
  """.format(conditions), filters, as_dict=True)
 
	for thr in q_laporan_thr_detail:
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
			"label": _("THR Jumlah"),
			"fieldtype": "Currency",
			"fieldname": "jumlah",
		},
	]

	return columns