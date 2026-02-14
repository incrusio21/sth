# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []

	query_l_phk = frappe.db.sql("""
		SELECT 
		pkp.employee_name as nama,
		ee.no_ktp as nik_ktp,
		ee.bank_ac_no as no_rek,
		ee.date_of_joining as tanggal_masuk_kerja,
		ee.relieving_date as tanggal_phk,
		ee.company as pt,
		pkp.dphk as dasar_phk,
		eilb.employee_name as yang_mengeluarkan_surat,
		pkp.grand_total as pesangon_kompensasi,
		pkp.persetujuan_1 as pers_1,
		pkp.persetujuan_2 as pers_2,
		pkp.persetujuan_3 as pers_3,
		pkp.persetujuan_4 as pers_4
		FROM `tabPerhitungan Kompensasi PHK` as pkp
		JOIN `tabEmployee` as ee ON ee.name = pkp.employee
		LEFT JOIN `tabEmployee` as eilb ON eilb.name = pkp.ilb
		WHERE pkp.company IS NOT NULL {}
  """.format(conditions), filters, as_dict=True)

	for emp in query_l_phk:
		data.append(emp)

	return columns, data

def get_condition(filters):
	conditions = ""

	if filters.get("pt"):
		conditions += " AND pkp.company = %(pt)s"

	if filters.get("unit"):
		conditions += " AND pkp.unit = %(unit)s"

	if filters.get("golongan"):
		conditions += " AND ee.grade = %(golongan)s"

	if filters.get("jabatan"):
		conditions += " AND ee.designation = %(jabatan)s"
  
	if filters.get("from_date") and filters.get("to_date"):
		conditions += " AND pkp.posting_date BETWEEN %(from_date)s AND %(to_date)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("NAMA"),
			"fieldtype": "Data",
			"fieldname": "nama",
		},
		{
			"label": _("NIK KTP"),
			"fieldtype": "Data",
			"fieldname": "nik_ktp",
		},
		{
			"label": _("NO REK"),
			"fieldtype": "Data",
			"fieldname": "no_rek",
		},
		{
			"label": _("TANGGAL MASUK KERJA"),
			"fieldtype": "Date",
			"fieldname": "tanggal_masuk_kerja",
		},
		{
			"label": _("TANGGAL PHK"),
			"fieldtype": "Date",
			"fieldname": "tanggal_phk",
		},
		{
			"label": _("PT"),
			"fieldtype": "Data",
			"fieldname": "pt",
		},
		{
			"label": _("DASAR PHK"),
			"fieldtype": "Data",
			"fieldname": "dasar_phk",
		},
		{
			"label": _("YANG MENGELUARKAN SURAT"),
			"fieldtype": "Data",
			"fieldname": "yang_mengeluarkan_surat",
		},
		{
			"label": _("PESANGON/KOMPENSASI"),
			"fieldtype": "Currency",
			"fieldname": "pesangon_kompensasi",
		},
		{
			"label": _("PERS 1"),
			"fieldtype": "Data",
			"fieldname": "pers_1",
		},
		{
			"label": _("PERS 2"),
			"fieldtype": "Data",
			"fieldname": "pers_2",
		},
		{
			"label": _("PERS 3"),
			"fieldtype": "Data",
			"fieldname": "pers_3",
		},
		{
			"label": _("PERS 4"),
			"fieldtype": "Data",
			"fieldname": "pers_4",
		},
	]

	return columns