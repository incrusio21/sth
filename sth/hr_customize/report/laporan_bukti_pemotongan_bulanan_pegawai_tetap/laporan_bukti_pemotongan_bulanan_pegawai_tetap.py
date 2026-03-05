# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = [
		{
			"masa_pajak": "test"
		}
	]

	return columns, data

def get_condition(filters):
	conditions = ""

	if filters.get("company"):
		conditions += " AND pi.company = %(company)s"

	return conditions

def get_columns(filters):
	columns = [
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
			"label": _("Status Pegawai"),
			"fieldtype": "Data",
			"fieldname": "status_pegawai",
		},
		{
			"label": _("NPWP/NIK/TIN"),
			"fieldtype": "Data",
			"fieldname": "npwp_nik_tin",
		},
		{
			"label": _("Nomor Passport"),
			"fieldtype": "Data",
			"fieldname": "nomor_passport",
		},
		{
			"label": _("Status"),
			"fieldtype": "Data",
			"fieldname": "status",
		},
		{
			"label": _("Posisi"),
			"fieldtype": "Data",
			"fieldname": "posisi",
		},
		{
			"label": _("Sertifikat/Fasilitas"),
			"fieldtype": "Data",
			"fieldname": "sertifikasi_fasilitas",
		},
		{
			"label": _("Kode Objek Pajak"),
			"fieldtype": "Data",
			"fieldname": "kode_objek_pajak",
		},
		{
			"label": _("Penghasilan Kotor"),
			"fieldtype": "Data",
			"fieldname": "penghasilan_kotor",
		},
		{
			"label": _("Tarif"),
			"fieldtype": "Data",
			"fieldname": "tarif",
		},
		{
			"label": _("ID TKU"),
			"fieldtype": "Data",
			"fieldname": "id_tku",
		},
		{
			"label": _("Tgl Pemotongan"),
			"fieldtype": "Date",
			"fieldname": "tgl_pemotongan",
		},
		{
			"label": _("TER A"),
			"fieldtype": "Data",
			"fieldname": "ter_a",
		},
		{
			"label": _("TER B"),
			"fieldtype": "Data",
			"fieldname": "ter_b",
		},
		{
			"label": _("TER C"),
			"fieldtype": "Data",
			"fieldname": "ter_c",
		},
	]

	return columns
