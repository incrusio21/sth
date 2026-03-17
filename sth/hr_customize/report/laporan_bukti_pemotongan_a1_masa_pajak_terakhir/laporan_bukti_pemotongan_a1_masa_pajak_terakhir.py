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
				COUNT(DISTINCT MONTH(ss.posting_date)) AS jumlah_slip,
				ss.employee_name,

				'No' AS pemberi_kerja_selanjutnya,

				MONTH(MIN(ss.posting_date)) AS masa_pajak_awal,
				MONTH(MAX(ss.posting_date)) AS masa_pajak_akhir,
				YEAR(MIN(ss.posting_date)) AS tahun_pajak,

				CASE 
						WHEN e.custom_citizenship_status = 'WNI' THEN 'Resident'
						ELSE 'Foreign'
				END AS wni_wna,

				e.passport_number AS no_paspor,
				e.no_ktp AS npwp,
				e.pkp_status AS status_ptkp,
				d.designation_name AS posisi,

				'21-100-01' AS kode_objek_pajak,

				CASE 
						WHEN COUNT(DISTINCT MONTH(ss.posting_date)) = 12 THEN 'FullYear'
						ELSE 'PartialYear'
				END AS status_bukti_potong,

				SUM(
						CASE 
								WHEN sd.salary_component = 'Gaji Pokok'
								AND sc.type = 'Earning'
								THEN sd.amount ELSE 0
						END
				) AS gaji,

				CASE 
						WHEN ssa.pph_21_gross_up = 1 THEN 'Yes'
						ELSE 'No'
				END AS opsi_gross_up,

				SUM(
						CASE 
								WHEN sd.salary_component = 'PPH21 TER Gross Up'
								AND sc.type = 'Earning'
								THEN sd.amount ELSE 0
						END
				) AS tunjangan_pph,

				SUM(
						CASE 
								WHEN (
										sd.salary_component IN ('Lembur','Natura')
										OR sd.salary_component LIKE '%%Premi%%'
								)
								AND sc.type = 'Earning'
								THEN sd.amount ELSE 0
						END
				) AS tunjangan_lainnya_lembur,

				0 AS honarorium,

				SUM(
						CASE 
								WHEN sc.name IN (
										'BPJS Kesehatan (Perusahaan)',
										'BPJS TK - JKM',
										'BPJS TK - JKK-RST',
										'BPJS TK - JKK-RSR',
										'BPJS TK - JKK-RT',
										'BPJS TK - JKK-RSD',
										'BPJS TK - JKK-RS',
										'PPH21 TER Gross Up'
								)
								AND sc.type = 'Earning'
								THEN sd.amount ELSE 0
						END
				) AS asuransi,

				0 AS natura,

				SUM(
						CASE 
								WHEN sd.salary_component IN ('THR Earning','Bonus Earning')
								THEN sd.amount ELSE 0
						END
				) AS tantiem_bonus_gratifikasi_thr,

				SUM(
						CASE 
								WHEN sc.name IN (
										'BPJS TK - JHT (Karyawan)',
										'BPJS TK - JP (Karyawan)'
								)
								AND sc.type = 'Deduction'
								THEN sd.amount ELSE 0
						END
				) AS iuran_pensiun_atau_biaya_tht_jht,

				0 AS zakat,

				'' AS nomor_bukti_potong_sebelumnya,
				'N/A' AS fasilitas_pajak,
				0 AS pph_pasal_21,

				cnd.nitku AS id_tku_pemotong,

				DATE_FORMAT(LAST_DAY(MAX(ss.posting_date)), '%%d/%%m/%%Y') AS tanggal_pemotong

		FROM `tabSalary Slip` ss

		JOIN `tabEmployee` e 
				ON e.name = ss.employee

		JOIN `tabDesignation` d 
				ON d.name = e.designation

		LEFT JOIN (
				SELECT employee, MAX(from_date) AS from_date
				FROM `tabSalary Structure Assignment`
				GROUP BY employee
		) latest_ssa
				ON latest_ssa.employee = ss.employee

		LEFT JOIN `tabSalary Structure Assignment` ssa
				ON ssa.employee = latest_ssa.employee
				AND ssa.from_date = latest_ssa.from_date

		LEFT JOIN `tabSalary Detail` sd 
				ON sd.parent = ss.name

		LEFT JOIN `tabSalary Component` sc 
				ON sc.name = sd.salary_component

		LEFT JOIN `tabCompany NITKU Detail` cnd
				ON cnd.parent = ss.company
				AND cnd.golongan = e.grade

		WHERE 
				ss.docstatus = 1
				{}

		GROUP BY 
				ss.employee,
				YEAR(ss.posting_date)

		ORDER BY 
				ss.employee_name;
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

	if filters.get("grade"):
		conditions += " AND e.grade = %(grade)s"

	if filters.get("employment_type"):
		conditions += " AND e.employment_type = %(employment_type)s"

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
