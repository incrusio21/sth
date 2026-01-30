# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []

	q_laporan_bpjs = frappe.db.sql("""
		SELECT
		e.employee_name as nama,
		dbe.no_ktp as no_ktp,
		d.designation_name as jabatan,
		dbe.gp as gp,
		dbe.beban_karyawan as beban_karyawan,
		dbe.beban_perusahaan as beban_perusahaan,
		dbe.jumlah as jumlah,
		e.custom_no_bpjs_ketenagakerjaan as bpjs_tk,
		e.custom_no_bpjs_kesehatan as bpjs_kes,
		e.custom_nama_ibu_kandung as nama_ibu_kandung,
		e.blood_group as gol_darah
		FROM `tabDaftar BPJS` as db
		JOIN `tabDaftar BPJS Employee` as dbe ON dbe.parent = db.name
		JOIN `tabEmployee` as e ON e.name = dbe.employee
		JOIN `tabDesignation` as d ON d.name = e.designation
		JOIN `tabSalary Structure Assignment` as ssa ON ssa.employee = e.name
		WHERE db.pt IS NOT NULL {}
		GROUP BY db.name, dbe.employee;
  """.format(conditions), filters, as_dict=True)

	for bpjs in q_laporan_bpjs:
		row = {
			"nama": bpjs.get("nama"),
			"no_ktp": bpjs.get("no_ktp"),
			"jabatan": bpjs.get("jabatan"),
			"gp": bpjs.get("gp"),
			"beban_karyawan": bpjs.get("beban_karyawan"),
			"beban_perusahaan": bpjs.get("beban_perusahaan"),
			"jumlah": bpjs.get("jumlah"),
			"nama_ibu_kandung": bpjs.get("nama_ibu_kandung"),
			"gol_darah": bpjs.get("gol_darah"),
		}
  
		if filters.get("bpjs_type"):
			if filters.get("bpjs_type") == "BPJS KES":
				row["no_bpjs_tk_kes"] = bpjs.get("bpjs_kes")
			elif filters.get("bpjs_type") == "BPJS TK":
				row["no_bpjs_tk_kes"] = bpjs.get("bpjs_tk")
			else:
				row["no_bpjs_tk_kes"] = "testing"

		data.append(row)

	return columns, data

def get_condition(filters):
	conditions = ""

	if filters.get("kode"):
		conditions += " AND db.set_up_bpjs = %(kode)s"

	if filters.get("company"):
		conditions += " AND db.pt = %(company)s"

	if filters.get("unit"):
		conditions += " AND db.unit = %(unit)s"

	if filters.get("bpjs_type"):
		conditions += " AND db.jenis_bpjs = %(bpjs_type)s"

	if filters.get("npp_no_bu"):
		conditions += " AND db.npp__no_bu = %(npp_no_bu)s"

	if filters.get("start_periode") and filters.get("end_periode"):
		conditions += " AND db.start_periode = %(start_periode)s AND db.end_periode = %(end_periode)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("Nama"),
			"fieldtype": "Data",
			"fieldname": "nama",
		},
		{
			"label": _("No KTP"),
			"fieldtype": "Data",
			"fieldname": "no_ktp",
		},
		{
			"label": _("Jabatan"),
			"fieldtype": "Data",
			"fieldname": "jabatan",
		},
		{
			"label": _("Gp"),
			"fieldtype": "Currency",
			"fieldname": "gp",
		},
		{
			"label": _("Beban Karyawan"),
			"fieldtype": "Currency",
			"fieldname": "beban_karyawan",
		},
		{
			"label": _("Beban Perusahaan"),
			"fieldtype": "Currency",
			"fieldname": "beban_perusahaan",
		},
		{
			"label": _("Jumlah"),
			"fieldtype": "Currency",
			"fieldname": "jumlah",
		},
		{
			"label": _("No BPJS TK/KES"),
			"fieldtype": "Data",
			"fieldname": "no_bpjs_tk_kes",
		},
		{
			"label": _("Nama Ibu Kandung"),
			"fieldtype": "Data",
			"fieldname": "nama_ibu_kandung",
		},
		{
			"label": _("Gol Darah"),
			"fieldtype": "Data",
			"fieldname": "gol_darah",
		},
		{
			"label": _("Keterangan"),
			"fieldtype": "Data",
			"fieldname": "keterangan",
		},
	]

	return columns