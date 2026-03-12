# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = []
 
	query_data = frappe.db.sql("""
		SELECT
		ss.name,
		MONTH(ss.posting_date) as masa_pajak,
		YEAR(ss.posting_date) as tahun_pajak,
		e.no_ktp as npwp,
		CONCAT(e.no_ktp, '000000') as id_tku_penerima_penghasilan,
		e.pkp_status as status_ptkp,
		'N/A' as fasilitas,
		'21-100-35' as kode_objek_pajak,
		ss.rounded_total as penghasilan,
		'100' as deemed,
		dt.tarif_pajak as tarif,
		"Other" as jenis_dok_referensi,
		DATE_FORMAT(LAST_DAY(ss.posting_date), '%%d%%m%%Y') as nomor_dok_referensi,
		DATE_FORMAT(LAST_DAY(ss.posting_date), '%%d/%%m/%%Y') as tanggal_dok_referensi,
		cnd.nitku as id_tku_pemotong,
		DATE_FORMAT(LAST_DAY(ss.posting_date), '%%d/%%m/%%Y') as tanggal_pemotong
		FROM `tabSalary Slip` as ss
		JOIN `tabEmployee` as e ON e.name = ss.employee
		JOIN `tabDetail Golongan TER` as dgt ON dgt.status_golongan = e.pkp_status 
		LEFT JOIN `tabDetail TER` as dt 
			ON dt.parent = dgt.parent
			AND ss.rounded_total >= dt.batas_bawah
			AND ss.rounded_total <= dt.batas_atas
		LEFT JOIN `tabCompany NITKU Detail` as cnd
			ON cnd.parent = ss.company
			AND cnd.golongan = e.grade
		WHERE e.employment_type != 'KARYAWAN TETAP' AND ss.docstatus = 1 {}
		ORDER BY MONTH(ss.posting_date);
  """.format(conditions), filters, as_dict=True)

	for row in query_data:
		data.append(row)

	return columns, data

def get_condition(filters):
	conditions = ""
	bulan_map = {
		"Januari": 1, "Februari": 2, "Maret": 3, "April": 4,
		"Mei": 5, "Juni": 6, "Juli": 7, "Agustus": 8,
		"September": 9, "Oktober": 10, "November": 11, "Desember": 12
	}

	if filters.get("company"):
		conditions += " AND ss.company = %(company)s"

	if filters.get("unit"):
		conditions += " AND ss.unit = %(unit)s"

	if filters.get("grade"):
		conditions += " AND e.grade = %(grade)s"

	if filters.get("employment_type"):
		conditions += " AND e.employment_type = %(employment_type)s"

	if filters.get("bulan"):
		filters["month_num"] = bulan_map.get(filters.get("bulan"), 1)
		conditions += " AND MONTH(ss.posting_date) = %(month_num)s"

	if filters.get("tahun"):
		conditions += " AND YEAR(ss.posting_date) = %(tahun)s"

	return conditions

def get_columns(filters):
	columns = [
		# {
		# 	"label": _("Slip"),
		# 	"fieldtype": "Data",
		# 	"fieldname": "name",
		# },
		{
			"label": _("Masa Pajak"),
			"fieldtype": "Data",
			"fieldname": "masa_pajak",
		},
		{
			"label": _("Tahun Pajak"),
			"fieldtype": "Data",
			"fieldname": "tahun_pajak",
		},
		{
			"label": _("NPWP"),
			"fieldtype": "Data",
			"fieldname": "npwp",
		},
		{
			"label": _("ID TKU Penerima Penghasilan"),
			"fieldtype": "Data",
			"fieldname": "id_tku_penerima_penghasilan",
		},
		{
			"label": _("Status PTKP"),
			"fieldtype": "Data",
			"fieldname": "status_ptkp",
		},
		{
			"label": _("Fasilitas"),
			"fieldtype": "Data",
			"fieldname": "fasilitas",
		},
		{
			"label": _("Kode Objek Pajak"),
			"fieldtype": "Data",
			"fieldname": "kode_objek_pajak",
		},
		{
			"label": _("Penghasilan"),
			"fieldtype": "Currency",
			"fieldname": "penghasilan",
		},
		{
			"label": _("Deemed"),
			"fieldtype": "Data",
			"fieldname": "deemed",
		},
		{
			"label": _("Tarif"),
			"fieldtype": "Data",
			"fieldname": "tarif",
		},
		{
			"label": _("Jenis Dok. Referensi"),
			"fieldtype": "Data",
			"fieldname": "jenis_dok_referensi",
		},
		{
			"label": _("Nomor Dok. Referensi"),
			"fieldtype": "Data",
			"fieldname": "nomor_dok_referensi",
		},
		{
			"label": _("Tanggal Dok. Referensi"),
			"fieldtype": "Data",
			"fieldname": "tanggal_dok_referensi",
		},
		{
			"label": _("ID TKU Pemotong"),
			"fieldtype": "Data",
			"fieldname": "id_tku_pemotong",
		},
		{
			"label": _("Tanggal Pemotongan"),
			"fieldtype": "Data",
			"fieldname": "tanggal_pemotong",
		},
		# {
		# 	"label": _("DPP"),
		# 	"fieldtype": "Data",
		# 	"fieldname": "dpp",
		# },
		# {
		# 	"label": _("JNS TARIF"),
		# 	"fieldtype": "Data",
		# 	"fieldname": "jns_tarif",
		# },
		# {
		# 	"label": _("TER A"),
		# 	"fieldtype": "Data",
		# 	"fieldname": "ter_a",
		# },
		# {
		# 	"label": _("TER B"),
		# 	"fieldtype": "Data",
		# 	"fieldname": "ter_b",
		# },
		# {
		# 	"label": _("TER C"),
		# 	"fieldtype": "Data",
		# 	"fieldname": "ter_c",
		# },
		# {
		# 	"label": _("PS17"),
		# 	"fieldtype": "Data",
		# 	"fieldname": "ps17",
		# },
		# {
		# 	"label": _("HARIAN"),
		# 	"fieldtype": "Data",
		# 	"fieldname": "harian",
		# },
		# {
		# 	"label": _("PESANGON"),
		# 	"fieldtype": "Data",
		# 	"fieldname": "pesangon",
		# },
		# {
		# 	"label": _("PENSIUN"),
		# 	"fieldtype": "Data",
		# 	"fieldname": "pensiunan",
		# },
	]

	return columns
