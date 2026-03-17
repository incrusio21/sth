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
				MONTH(ss.posting_date) AS masa_pajak,
				YEAR(ss.posting_date) AS tahun_pajak,

				CASE 
						WHEN e.custom_citizenship_status = 'WNI' THEN 'Resident'
						ELSE 'Foreign'
				END AS status_pegawai,

				e.no_ktp AS npwp_nik_tin,
				e.passport_number AS nomor_passport,
				e.pkp_status AS status,
				d.designation_name AS posisi,

				'N/A' AS sertifikasi_fasilitas,
				'21-100-01' AS kode_objek_pajak,

				sd_total.penghasilan_kotor AS penghasilan_kotor,

				dt.tarif_pajak AS tarif,
				cnd.nitku AS id_tku,

				DATE_FORMAT(LAST_DAY(ss.posting_date), '%%d/%%m/%%Y') AS tanggal_pemotong

		FROM `tabSalary Slip` ss

		JOIN `tabEmployee` e 
				ON e.name = ss.employee

		JOIN `tabDesignation` d 
				ON d.name = e.designation

		LEFT JOIN (
				SELECT 
						parent,
						SUM(amount) AS penghasilan_kotor
				FROM `tabSalary Detail`
				WHERE salary_component IN (
						'Gaji Pokok',
						'Upah Panen',
						'Upah Perawatan',
						'Upah Traksi',
						'HKnE',
						'Lembur',
						'Natura',
						'Premi Brondolan',
						'Premi Kehadiran',
						'Premi Tutup Buku',
						'Premi Angkut',
						'Premi Supervisi',
						'INCENTIF HKE PANEN',
						'INCENTIF OUTPUT',
						'Subsidi Tambahan',
						'Rapel',
						'THR Earning',
						'Bonus Earning',
						'BPJS Kesehatan (Perusahaan)',
						'BPJS TK - JKM',
						'BPJS TK - JKK-RST',
						'BPJS TK - JKK-RSR',
						'BPJS TK - JKK-RT',
						'BPJS TK - JKK-RSD',
						'BPJS TK - JKK-RS',
						'PPH21 TER Gross Up'
				)
				GROUP BY parent
		) sd_total
				ON sd_total.parent = ss.name

		JOIN `tabDetail Golongan TER` dgt 
				ON dgt.status_golongan = e.pkp_status

		LEFT JOIN `tabDetail TER` dt
				ON dt.parent = dgt.parent
				AND sd_total.penghasilan_kotor BETWEEN dt.batas_bawah AND dt.batas_atas

		LEFT JOIN `tabCompany NITKU Detail` cnd
				ON cnd.parent = ss.company
				AND cnd.golongan = e.grade

		WHERE 
				e.employment_type = 'KARYAWAN TETAP'
				AND ss.docstatus = 1
				{}

		GROUP BY ss.name

		ORDER BY ss.posting_date;
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

	if filters.get("designation"):
		conditions += " AND ss.designation = %(designation)s"

	if filters.get("bulan"):
		filters["month_num"] = bulan_map.get(filters.get("bulan"), 1)
		conditions += " AND MONTH(ss.posting_date) = %(month_num)s"

	if filters.get("tahun"):
		conditions += " AND YEAR(ss.posting_date) = %(tahun)s"

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
			"fieldtype": "Currency",
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
			"label": _("Tanggal Pemotongan"),
			"fieldtype": "Data",
			"fieldname": "tanggal_pemotong",
		},
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
	]

	return columns
