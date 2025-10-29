# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	columns = get_columns(filters)
	data = []
	conditions = get_condition(filters)

	query_dbt = frappe.db.sql("""
		SELECT
		e.name,
		e.grade as employee_grade,
		e.custom_nip as no_pegawai,
		e.employee_name as nama_lengkap,
		e.cell_number as hp,
		e.personal_email as email,
		e.custom_place_of_birth as tempat_lahir,
		DATE_FORMAT(e.date_of_birth, '%%d-%%m-%%Y') as tanggal_lahir,
		e.custom_nama_ibu_kandung as nama_ibu_kandung,
		CASE
			WHEN e.no_ktp THEN 'Ktp'
			ELSE 'Passport'
		END as jenis_identitas,
		CASE
			WHEN e.no_ktp THEN e.no_ktp 
			ELSE e.passport_number
		END as nomor_identitas,
		CASE
				WHEN e.no_ktp IS NOT NULL AND e.no_ktp <> '' THEN '31-12-3000'
				ELSE DATE_FORMAT(e.valid_upto, '%%d-%%m-%%Y')
		END AS masa_laku_identitas,
		CASE
			WHEN e.gender = 'Male' THEN 'L'
			WHEN e.gender = 'Female' THEN 'P'
			ELSE e.gender
		END as jenis_kelamin,
		CASE
			WHEN e.personal_email IS NOT NULL THEN 'E'
			ELSE 'S'
		END as surat_menyurat_ke,
		CASE 
			WHEN e.marital_status = 'Married' THEN 'Y'
			ELSE 'T'
		END as status_kawin,
		CASE 
			WHEN e.blood_group  IN ('A+', 'A-') THEN 'A'
			WHEN e.blood_group  IN ('B+', 'B-') THEN 'B'
			WHEN e.blood_group  IN ('AB+', 'AB-') THEN 'AB'
			WHEN e.blood_group  IN ('O+', 'O-') THEN 'O'
			ELSE 'Belum isi'
		END as golongan_darah,
		e.npwp as npwp,
		n.nc as kode_negara,
		e.ctc as upah,
		e.permanent_address as alamat,
		e.custom_pos_code as kode_pos,
		e.custom_location as lokasi_pekerjaan,
		CASE 
			WHEN e.contract_end_date THEN 'PKWT'
			ELSE 'PKWTT'
		END AS status_pegawai,
		DATE_FORMAT(e.date_of_joining, '%%d-%%m-%%Y') as tgl_awal_bekerja,
		DATE_FORMAT(e.contract_end_date, '%%d-%%m-%%Y') as tgl_akhir_kontrak
		FROM `tabEmployee` as e
		LEFT JOIN `tabNationality` as n ON n.name = e.custom_nationality
		WHERE e.relieving_date IS NULL {};
	""".format(conditions), filters, as_dict=True)

	for item in query_dbt:
		row = {}
		for key, value in item.items():
			row[key] = value
		data.append(row)

	return columns, data

def get_condition(filters):
	conditions = "AND e.company = %(company)s"

	if filters.get("employee_grade"):
		conditions += " AND e.grade = %(employee_grade)s"
	
	if filters.get("employment_type"):
		conditions += " AND e.employment_type = %(employment_type)s"
	
	if filters.get("from_date") and filters.get("to_date"):
		conditions += " AND e.date_of_joining BETWEEN %(from_date)s AND %(to_date)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("NO_PEGAWAI"),
			"fieldtype": "Data",
			"fieldname": "no_pegawai",
		},
		{
			"label": _("NAMA_LENGKAP"),
			"fieldtype": "Data",
			"fieldname": "nama_lengkap"
		},
		{
			"label": _("GELAR"),
			"fieldtype": "Data",
			"fieldname": "gelar"
		},
		{
			"label": _("TELEPON_AREA_RUMAH"),
			"fieldtype": "Data",
			"fieldname": "telepon_area_rumah"
		},
		{
			"label": _("TELEPON_RUMAH"),
			"fieldtype": "Data",
			"fieldname": "telepon_rumah"
		},
		{
			"label": _("TELEPON_AREA_KANTOR"),
			"fieldtype": "Data",
			"fieldname": "telepon_area_kantor"
		},
		{
			"label": _("TELEPON_KANTOR"),
			"fieldtype": "Data",
			"fieldname": "telepon_kantor"
		},
		{
			"label": _("TELEPON_EXT_KANTOR"),
			"fieldtype": "Data",
			"fieldname": "telepon_ext_kantor"
		},
		{
			"label": _("HP"),
			"fieldtype": "Data",
			"fieldname": "hp"
		},
		{
			"label": _("EMAIL"),
			"fieldtype": "Data",
			"fieldname": "email"
		},
		{
			"label": _("TEMPAT_LAHIR"),
			"fieldtype": "Data",
			"fieldname": "tempat_lahir"
		},
		{
			"label": _("TANGGAL_LAHIR"),
			"fieldtype": "Data",
			"fieldname": "tanggal_lahir"
		},
		{
			"label": _("NAMA_IBU_KANDUNG"),
			"fieldtype": "Data",
			"fieldname": "nama_ibu_kandung"
		},
		{
			"label": _("JENIS_IDENTITAS"),
			"fieldtype": "Data",
			"fieldname": "jenis_identitas"
		},
		{
			"label": _("NOMOR_IDENTITAS"),
			"fieldtype": "Data",
			"fieldname": "nomor_identitas"
		},
		{
			"label": _("MASA_LAKU_IDENTITAS"),
			"fieldtype": "Data",
			"fieldname": "masa_laku_identitas"
		},
		{
			"label": _("JENIS_KELAMIN"),
			"fieldtype": "Data",
			"fieldname": "jenis_kelamin"
		},
		{
			"label": _("SURAT_MENYURAT_KE"),
			"fieldtype": "Data",
			"fieldname": "surat_menyurat_ke"
		},
		{
			"label": _("TANGGAL_KEPESERTAAN"),
			"fieldtype": "Data",
			"fieldname": "tanggal_kepersetaan"
		},
		{
			"label": _("STATUS_KAWIN"),
			"fieldtype": "Data",
			"fieldname": "status_kawin"
		},
		{
			"label": _("GOLONGAN_DARAH"),
			"fieldtype": "Data",
			"fieldname": "golongan_darah"
		},
		{
			"label": _("NPWP"),
			"fieldtype": "Data",
			"fieldname": "npwp"
		},
		{
			"label": _("KODE_NEGARA"),
			"fieldtype": "Data",
			"fieldname": "kode_negara"
		},
		{
			"label": _("UPAH"),
			"fieldtype": "Data",
			"fieldname": "upah"
		},
		{
			"label": _("ALAMAT"),
			"fieldtype": "Data",
			"fieldname": "alamat"
		},
		{
			"label": _("KODE_POS"),
			"fieldtype": "Data",
			"fieldname": "kode_pos"
		},
		{
			"label": _("LOKASI_PEKERJAAN"),
			"fieldtype": "Data",
			"fieldname": "lokasi_pekerjaan"
		},
		{
			"label": _("STATUS_PEGAWAI"),
			"fieldtype": "Data",
			"fieldname": "status_pegawai"
		},
		{
			"label": _("TGL_AWAL_BEKERJA"),
			"fieldtype": "Data",
			"fieldname": "tgl_awal_bekerja"
		},
		{
			"label": _("TGL_AKHIR_KONTRAK"),
			"fieldtype": "Data",
			"fieldname": "tgl_akhir_kontrak"
		},
	]

	return columns