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
		COUNT(DISTINCT MONTH(ss.posting_date)) as jumlah_slip,
		ss.employee_name,
		'No' as pemberi_kerja_selanjutnya,
		MONTH(MIN(ss.posting_date)) as masa_pajak_awal,
		MONTH(MAX(ss.posting_date)) as masa_pajak_akhir,
		YEAR(MIN(ss.posting_date)) as tahun_pajak,
		CASE 
				WHEN e.custom_citizenship_status = "WNI" THEN "Resident"
				ELSE "Foreign"
		END as wni_wna,
		e.passport_number as no_paspor,
		e.no_ktp as npwp,
		e.pkp_status as status_ptkp,
		d.designation_name as posisi,
		'21-100-01' as kode_objek_pajak,
		CASE 
				WHEN COUNT(DISTINCT MONTH(ss.posting_date)) = 12 THEN "FullYear"
				ELSE "PartialYear"
		END as status_bukti_potong,
		CASE 
				WHEN ssa.pph_21_gross_up = 1 THEN "Yes"
				ELSE "No"
		END as opsi_gross_up,
		0 as tunjangan_pph,
		SUM(
				CASE 
						WHEN sd.salary_component = 'Lembur' THEN sd.amount
						ELSE 0
				END
		) as tunjangan_lainnya_lembur,
		0 as honarorium,
		SUM(
				CASE 
						WHEN sc.name LIKE '%%BPJS%%' AND sc.type = 'Earning'
						THEN sd.amount
						ELSE 0
				END
		) as asuransi,
		SUM(
				CASE 
						WHEN sd.salary_component = 'Natura' AND sc.type = 'Earning'
						THEN sd.amount
						ELSE 0
				END
		) as natura,
		SUM(
				CASE 
						WHEN sd.salary_component IN ('THR Earning', 'Bonus Earning')
						THEN sd.amount
						ELSE 0
				END
		) as tantiem_bonus_gratifikasi_thr,
		SUM(
				CASE 
						WHEN sc.name LIKE '%%BPJS%%' AND sc.type = 'Deduction'
						THEN sd.amount
						ELSE 0
				END
		) as iuran_pensiun_atau_biaya_tht_jht,
		0 as zakat,
		'' as nomor_bukti_potong_sebelumnya,
		'N/A' as fasilitas_pajak,
		0 as pph_pasal_21,
		cnd.nitku as id_tku_pemotong,
		DATE_FORMAT(LAST_DAY(MAX(ss.posting_date)), '%%d/%%m/%%Y') as tanggal_pemotong

		FROM `tabSalary Slip` as ss
		JOIN `tabEmployee` as e ON e.name = ss.employee 
		JOIN `tabDesignation` as d ON d.name = e.designation
		JOIN `tabSalary Structure Assignment` as ssa 
			ON ssa.employee = ss.employee
			AND ssa.from_date = (
					SELECT MAX(ssa2.from_date)
					FROM `tabSalary Structure Assignment` ssa2
					WHERE ssa2.employee = ss.employee
		)
		LEFT JOIN `tabSalary Detail` as sd ON sd.parent = ss.name
		LEFT JOIN `tabSalary Component` sc ON sc.name = sd.salary_component
		LEFT JOIN `tabCompany NITKU Detail` as cnd
			ON cnd.parent = ss.company
			AND cnd.golongan = e.grade
		WHERE ss.docstatus = 1 {}
		GROUP BY ss.employee, ss.employee_name, YEAR(ss.posting_date)
		ORDER BY ss.employee_name;
  """.format(conditions), filters, as_dict=True)

	for row in query_data:
		data.append(row)

	return columns, data

def get_condition(filters):
	conditions = ""

	if filters.get("company"):
		conditions += " AND ss.company = %(company)s"

	if filters.get("unit"):
		conditions += " AND ss.unit = %(unit)s"

	if filters.get("tahun"):
		conditions += " AND YEAR(ss.posting_date) = %(tahun)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("Pemberi Kerja Selanjutnya"),
			"fieldtype": "Data",
			"fieldname": "pemberi_kerja_selanjutnya",
		},
		{
			"label": _("Masa Pajak Awal"),
			"fieldtype": "Data",
			"fieldname": "masa_pajak_awal",
		},
		{
			"label": _("Masa Pajak Akhir"),
			"fieldtype": "Data",
			"fieldname": "masa_pajak_akhir",
		},
		{
			"label": _("Tahun Pajak"),
			"fieldtype": "Data",
			"fieldname": "tahun_pajak",
		},
		{
			"label": _("WNI/WNA"),
			"fieldtype": "Data",
			"fieldname": "wni_wna",
		},
		{
			"label": _("No. Paspor"),
			"fieldtype": "Data",
			"fieldname": "no_paspor",
		},
		{
			"label": _("NPWP"),
			"fieldtype": "Data",
			"fieldname": "npwp",
		},
		{
			"label": _("Status PTKP"),
			"fieldtype": "Data",
			"fieldname": "status_ptkp",
		},
		{
			"label": _("Posisi"),
			"fieldtype": "Data",
			"fieldname": "posisi",
		},
		{
			"label": _("Kode Objek Pajak"),
			"fieldtype": "Data",
			"fieldname": "kode_objek_pajak",
		},
		{
			"label": _("Status Bukti Potong"),
			"fieldtype": "Data",
			"fieldname": "status_bukti_potong",
		},
		{
			"label": _("Jumlah Bulan Bekerja"),
			"fieldtype": "Data",
			"fieldname": "jumlah_bulan_bekerja",
		},
		{
			"label": _("Gaji"),
			"fieldtype": "Currency",
			"fieldname": "gaji",
		},
		{
			"label": _("Opsi Gross Up"),
			"fieldtype": "Data",
			"fieldname": "opsi_gross_up",
		},
		{
			"label": _("Tunjangan PPh"),
			"fieldtype": "Currency",
			"fieldname": "tunjangan_pph",
		},
		{
			"label": _("Tunjangan Lainnya / Lembur"),
			"fieldtype": "Currency",
			"fieldname": "tunjangan_lainnya_lembur",
		},
		{
			"label": _("Honorarium"),
			"fieldtype": "Currency",
			"fieldname": "honarorium",
		},
		{
			"label": _("Asuransi"),
			"fieldtype": "Currency",
			"fieldname": "asuransi",
		},
		{
			"label": _("Natura"),
			"fieldtype": "Currency",
			"fieldname": "natura",
		},
		{
			"label": _("Tantiem, Bonus, Gratifikasi, THR"),
			"fieldtype": "Currency",
			"fieldname": "tantiem_bonus_gratifikasi_thr",
		},
		{
			"label": _("Iuran Pensiun atau Biaya THT/JHT"),
			"fieldtype": "Currency",
			"fieldname": "iuran_pensiun_atau_biaya_tht_jht",
		},
		{
			"label": _("Zakat"),
			"fieldtype": "Currency",
			"fieldname": "zakat",
		},
		{
			"label": _("Nomor Bukti Potong Sebelumnya"),
			"fieldtype": "Data",
			"fieldname": "nomor_bukti_potong_sebelumnya",
		},
		{
			"label": _("Fasilitas Pajak"),
			"fieldtype": "Data",
			"fieldname": "fasilitas_pajak",
		},
		{
			"label": _("PPh Pasal 21*"),
			"fieldtype": "Data",
			"fieldname": "pph_pasal_21",
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
	]

	return columns
