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
		e.name as nik,
		e.employee_name as nama,
		e.image as pas_foto,
		d.designation_name as nama_jabatan,
		e.grade as golongan,
		e.employment_type as status_level,
		e.unit as lokasi_tugas,
		e.company as perusahaan,
		e.no_ktp as no_ktp,
		e.custom_no_kartu_keluarga as no_kk,
		e.npwp as no_npwp,
		e.bank_name as nama_bank,
		e.bank_ac_no as no_rek
		FROM `tabEmployee` as e
		JOIN `tabDesignation` as d ON d.name = e.designation
  	WHERE e.company IS NOT NULL {};
	""".format(conditions), filters, as_dict=True)

	# employee = sorted(query_l_daftar_karyawan, key=lambda x: (
  #   x.get("pt") or "",
  #   x.get("unit") or "",
  #   x.get("golongan") or "",
  #   x.get("status_level") or ""
	# ))

	# last_pt = None
	# last_unit = None
	# last_golongan = None

	# for d in employee:
	# 	row = d.copy()

	# 	# PT
	# 	if d["pt"] == last_pt:
	# 			row["pt"] = ""
	# 	else:
	# 			last_pt = d["pt"]
	# 			last_unit = None
	# 			last_golongan = None

	# 	# Unit
	# 	if d["unit"] == last_unit:
	# 			row["unit"] = ""
	# 	else:
	# 			last_unit = d["unit"]
	# 			last_golongan = None

	# 	# Golongan
	# 	if d["golongan"] == last_golongan:
	# 			row["golongan"] = ""
	# 	else:
	# 			last_golongan = d["golongan"]

	# 	data.append(row)

	for emp in query_l_daftar_karyawan:
		data.append(emp)
	# data.append({
	# 	"status_level": "Total",
	# 	"aktif": sum(d.get("aktif", 0) for d in data),
	# 	"keluar": sum(d.get("keluar", 0) for d in data),
	# })

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
			"label": _("No Induk Karyawan"),
			"fieldtype": "Data",
			"fieldname": "nik",
		},
		{
			"label": _("Nama"),
			"fieldtype": "Data",
			"fieldname": "nama",
		},
		{
			"label": _("Pas Photo"),
			"fieldtype": "Data",
			"fieldname": "pas_foto",
		},
		{
			"label": _("Nama Jabatan"),
			"fieldtype": "Data",
			"fieldname": "nama_jabatan",
		},
		{
			"label": _("Golongan"),
			"fieldtype": "Data",
			"fieldname": "golongan",
		},
		{
			"label": _("Status/level"),
			"fieldtype": "Data",
			"fieldname": "status_level",
		},
		{
			"label": _("Lokasi Tugas"),
			"fieldtype": "Data",
			"fieldname": "lokasi_tugas",
		},
		{
			"label": _("Perusahaan"),
			"fieldtype": "Data",
			"fieldname": "perusahaan",
		},
		{
			"label": _("No.KTP"),
			"fieldtype": "Data",
			"fieldname": "no_ktp",
		},
		{
			"label": _("Dok KTP"),
			"fieldtype": "Data",
			"fieldname": "dok_ktp",
		},
		{
			"label": _("No. KK"),
			"fieldtype": "Data",
			"fieldname": "no_kk",
		},
		{
			"label": _("Dok KK"),
			"fieldtype": "Data",
			"fieldname": "dok_kk",
		},
		{
			"label": _("No. NPWP"),
			"fieldtype": "Data",
			"fieldname": "no_npwp",
		},
		{
			"label": _("Dok NPWP"),
			"fieldtype": "Data",
			"fieldname": "dok_npwp",
		},
		{
			"label": _("Nama Bank"),
			"fieldtype": "Data",
			"fieldname": "nama_bank",
		},
		{
			"label": _("No Rek"),
			"fieldtype": "Data",
			"fieldname": "no_rek",
		},
		{
			"label": _("Dok Bank"),
			"fieldtype": "Data",
			"fieldname": "dok_bank",
		},
		{
			"label": _("No.Paspor"),
			"fieldtype": "Data",
			"fieldname": "no_paspor",
		},
		{
			"label": _("Dok Paspor"),
			"fieldtype": "Data",
			"fieldname": "dok_paspor",
		},
		{
			"label": _("No BPJS JHT,JKK,JKM"),
			"fieldtype": "Data",
			"fieldname": "no_bpjs_jht_jkk_jkm",
		},
		{
			"label": _("No BPJS Pensiun"),
			"fieldtype": "Data",
			"fieldname": "no_bpjs_pensiun",
		},
		{
			"label": _("Dok BPJS TK"),
			"fieldtype": "Data",
			"fieldname": "dok_bpjs_tk",
		},
		{
			"label": _("No BPJS Kes"),
			"fieldtype": "Data",
			"fieldname": "no_bpjs_kes",
		},
		{
			"label": _("Dok BPJS Kes"),
			"fieldtype": "Data",
			"fieldname": "dok_bpjs_kes",
		},
		{
			"label": _("Pendidikan"),
			"fieldtype": "Data",
			"fieldname": "pendidikan",
		},
		{
			"label": _("Status Pajak"),
			"fieldtype": "Data",
			"fieldname": "status_pajak",
		},
		{
			"label": _("Status Perkawinan"),
			"fieldtype": "Data",
			"fieldname": "status_perkawinan",
		},
		{
			"label": _("Tanggal Masuk"),
			"fieldtype": "Date",
			"fieldname": "tanggal_masuk",
		},
		{
			"label": _("Masa Kerja (Tahun)"),
			"fieldtype": "Data",
			"fieldname": "masa_kerja",
		},
		{
			"label": _("Tanggal Lahir"),
			"fieldtype": "Date",
			"fieldname": "tanggal_lahir",
		},
		{
			"label": _("Warga Negara"),
			"fieldtype": "Data",
			"fieldname": "warga_negara",
		},
		{
			"label": _("Jenis Kelamin"),
			"fieldtype": "Data",
			"fieldname": "jenis_kelamin",
		},
		{
			"label": _("Tanggal Menikah"),
			"fieldtype": "Date",
			"fieldname": "tanggal_menikah",
		},
		{
			"label": _("Agama"),
			"fieldtype": "Data",
			"fieldname": "agama",
		},
		{
			"label": _("Agama Group THR"),
			"fieldtype": "Data",
			"fieldname": "agama_group_thr",
		},
		{
			"label": _("Suku"),
			"fieldtype": "Data",
			"fieldname": "suku",
		},
		{
			"label": _("Alamat Aktif"),
			"fieldtype": "Data",
			"fieldname": "alamat_aktif",
		},
		{
			"label": _("Kab/Kota"),
			"fieldtype": "Data",
			"fieldname": "kab_kota",
		},
		{
			"label": _("Provinsi"),
			"fieldtype": "Data",
			"fieldname": "provinsi",
		},
		{
			"label": _("Kode Pos"),
			"fieldtype": "Data",
			"fieldname": "kode_pos",
		},
		{
			"label": _("No HP"),
			"fieldtype": "Data",
			"fieldname": "no_hp",
		},
		{
			"label": _("Telepon Darurat"),
			"fieldtype": "Data",
			"fieldname": "telepon_darurat",
		},
		{
			"label": _("Lokasi Penerimaan"),
			"fieldtype": "Data",
			"fieldname": "lokasi_penerimaan",
		},
		{
			"label": _("Lokasi Cuti"),
			"fieldtype": "Data",
			"fieldname": "lokasi_cuti",
		},
		{
			"label": _("Ibu Kandung"),
			"fieldtype": "Data",
			"fieldname": "ibu_kandung",
		},
		{
			"label": _("Tanggal Keluar"),
			"fieldtype": "Date",
			"fieldname": "tanggal_keluar",
		},
		{
			"label": _("CV"),
			"fieldtype": "Data",
			"fieldname": "cv",
		},
		{
			"label": _("Aplikasi Form"),
			"fieldtype": "Data",
			"fieldname": "aplikasi_form",
		},
		{
			"label": _("Ijazah"),
			"fieldtype": "Data",
			"fieldname": "ijazah",
		},
		{
			"label": _("Surat Ket Kerja"),
			"fieldtype": "Data",
			"fieldname": "surat_ket_kerja",
		},
		{
			"label": _("Pelatihan Lainnya"),
			"fieldtype": "Data",
			"fieldname": "pelatihan_lainnya",
		},
	]

	return columns
