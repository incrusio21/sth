# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = get_data(conditions, filters)

	return columns, data

def get_data(conditions, filters):
	slips = frappe.db.sql("""
		SELECT
			ss.name AS slip,
			e.divisi,
			e.name AS nik,
			e.employee_name AS nama_karyawan,
			e.employment_type AS jabatan,
			e.grade AS tipe_karyawan,
			e.pkp_status AS status_pajak,
			e.bank_ac_no AS no_rekening,
			ss.gross_pay AS total_pendapatan,
			ss.total_deduction AS total_potongan,
			ss.net_pay AS gaji_bersih
		FROM `tabSalary Slip` ss
		INNER JOIN `tabEmployee` e ON e.name = ss.employee
		WHERE ss.company IS NOT NULL {}
	""".format(conditions), filters, as_dict=True)

	details = frappe.db.sql("""
		SELECT parent, salary_component, amount
		FROM `tabSalary Detail`
	""", as_dict=True)

	lembur_map = frappe.db.sql("""
		SELECT
			employee,
			COALESCE(SUM(overtime_total), 0) AS total_jam_lembur
		FROM `tabLembur List`
		GROUP BY employee
	""", as_dict=True)

	detail_map = {}
	for d in details:
		detail_map.setdefault(d.parent, {})[frappe.scrub(d.salary_component)] = d.amount
  
	lembur_map = {
		l.employee: l.total_jam_lembur
		for l in lembur_map
	}

	for s in slips:
		s.update(detail_map.get(s.slip, {}))
		s["total_jam_lembur"] = lembur_map.get(s.nik, 0)

	return slips

def get_condition(filters):
	conditions = ""

	if filters.get("unit"):
		conditions += " AND e.unit = %(unit)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("Divisi"),
			"fieldtype": "Data",
			"fieldname": "divisi",
		},
		{
			"label": _("NIK"),
			"fieldtype": "Data",
			"fieldname": "nik",
		},
		{
			"label": _("Nama Karyawan"),
			"fieldtype": "Data",
			"fieldname": "nama_karyawan",
		},
		{
			"label": _("Jabatan"),
			"fieldtype": "Data",
			"fieldname": "jabatan",
		},
		{
			"label": _("Tipe Karyawan"),
			"fieldtype": "Data",
			"fieldname": "tipe_karyawan",
		},
		{
			"label": _("Status Pajak"),
			"fieldtype": "Data",
			"fieldname": "status_pajak",
		},
		{
			"label": _("No. Rekening"),
			"fieldtype": "Data",
			"fieldname": "no_rekening",
		},
		{
			"label": _("Total Jam Lembur"),
			"fieldtype": "Data",
			"fieldname": "total_jam_lembur",
		},
	]

	q_column_earning = frappe.db.sql("""
		SELECT sc.name FROM `tabSalary Component` as sc WHERE sc.type = 'Earning';
  """, as_dict=True)
	q_column_deduction = frappe.db.sql("""
		SELECT sc.name FROM `tabSalary Component` as sc WHERE sc.type = 'Deduction';
  """, as_dict=True)

	for earning in q_column_earning:
		columns.append({
			"label": earning.name,
			"fieldtype": "Currency",
			"fieldname": frappe.scrub(earning.name),
		})
  
	columns.append({
		"label": _("TOTAL PENDAPATAN"),
		"fieldtype": "Currency",
		"fieldname": "total_pendapatan",
	})

	for deduction in q_column_deduction:
		columns.append({
			"label": deduction.name,
			"fieldtype": "Currency",
			"fieldname": frappe.scrub(deduction.name),
		})

	columns.append({
		"label": _("Total Potongan"),
		"fieldtype": "Currency",
		"fieldname": "total_potongan",
	})

	columns.append({
		"label": _("GAJI BERSIH"),
		"fieldtype": "Currency",
		"fieldname": "gaji_bersih",
	})

	return columns