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
		e.custom_foto_ktp as dok_ktp,
		e.custom_no_kartu_keluarga as no_kk,
		e.custom_foto_kk as dok_kk,
		e.npwp as no_npwp,
		e.custom_foto_npwp as dok_npwp,
		e.bank_name as nama_bank,
		e.bank_ac_no as no_rek,
		e.custom_bank_book_document as dok_bank,
		e.passport_number as no_paspor,
		e.custom_passport_document_upload as dok_paspor,
		e.custom_no_bpjs_ketenagakerjaan as no_bpjs_jht_jkk_jkm,
		e.custom_foto_bpjs_ketenagakerjaan as dok_bpjs_tk,
		e.custom_no_bpjs_kesehatan as no_bpjs_kes,
		e.custom_document_health_insurance as dok_bpjs_kes,
		(SELECT ee.school_univ FROM `tabEmployee Education` as ee WHERE ee.parent = e.name LIMIT 1) as pendidikan,
		e.pkp_status as status_pajak,
		e.marital_status as status_perkawinan,
  	e.date_of_joining as tanggal_masuk,
		e.custom_employment_tenure as masa_kerja,
		e.date_of_birth as tanggal_lahir,
		e.custom_nationality as warga_negara,
		e.gender as jenis_kelamin,
		e.custom_religion as agama,
		e.custom_religion_group as agama_group_thr,
		e.custom_suku as suku,
		e.current_address as alamat_aktif,
		e.cell_number as no_hp,
		e.custom_nama_ibu_kandung as ibu_kandung,
		e.relieving_date as tanggal_keluar,
		e.custom_cv as cv,
		e.custom_aplikasi_form as aplikasi_form,
		e.custom_fotocopy_ijasah as ijazah,
		e.custom_surat_keterangan_kerja as surat_ket_kerja,
		e.custom_pelatihan_lainnya as pelatihan_lainnya
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

	if filters.get("divisi"):
		conditions += " AND e.divisi = %(divisi)s"

	if filters.get("golongan"):
		conditions += " AND e.designation = %(golongan)s"

	if filters.get("status_karyawan"):
		conditions += " AND e.status = %(status_karyawan)s"

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
			"fieldtype": "Attach Image",
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
			"fieldtype": "Attach Image",
			"fieldname": "dok_ktp",
		},
		{
			"label": _("No. KK"),
			"fieldtype": "Data",
			"fieldname": "no_kk",
		},
		{
			"label": _("Dok KK"),
			"fieldtype": "Attach Image",
			"fieldname": "dok_kk",
		},
		{
			"label": _("No. NPWP"),
			"fieldtype": "Data",
			"fieldname": "no_npwp",
		},
		{
			"label": _("Dok NPWP"),
			"fieldtype": "Attach Image",
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
			"fieldtype": "Attach Image",
			"fieldname": "dok_bank",
		},
		{
			"label": _("No.Paspor"),
			"fieldtype": "Data",
			"fieldname": "no_paspor",
		},
		{
			"label": _("Dok Paspor"),
			"fieldtype": "Attach Image",
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
			"fieldtype": "Attach Image",
			"fieldname": "dok_bpjs_tk",
		},
		{
			"label": _("No BPJS Kes"),
			"fieldtype": "Data",
			"fieldname": "no_bpjs_kes",
		},
		{
			"label": _("Dok BPJS Kes"),
			"fieldtype": "Attach Image",
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
			"fieldtype": "Attach Image",
			"fieldname": "cv",
		},
		{
			"label": _("Aplikasi Form"),
			"fieldtype": "Attach Image",
			"fieldname": "aplikasi_form",
		},
		{
			"label": _("Ijazah"),
			"fieldtype": "Attach Image",
			"fieldname": "ijazah",
		},
		{
			"label": _("Surat Ket Kerja"),
			"fieldtype": "Attach Image",
			"fieldname": "surat_ket_kerja",
		},
		{
			"label": _("Pelatihan Lainnya"),
			"fieldtype": "Attach Image",
			"fieldname": "pelatihan_lainnya",
		},
	]

	return columns
