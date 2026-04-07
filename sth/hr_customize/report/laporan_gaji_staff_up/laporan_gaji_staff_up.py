import frappe
from frappe import _

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_columns():
  return [
		{
			"fieldname": "id_karyawan",
			"label": _("ID KARYAWAN"),
			"fieldtype": "Data",
			"width": 200
		},
		{
			"fieldname": "nama_karyawan",
			"label": _("Nama Karyawan"),
			"fieldtype": "Data",
			"width": 200
		},
		{
			"fieldname": "agama",
			"label": _("AGAMA"),
			"fieldtype": "Data",
			"width": 200
		},
		{
			"fieldname": "tanggal_masuk_kerja",
			"label": _("TANGGAL MASUK KERJA"),
			"fieldtype": "Date",
			"width": 200
		},
		{
			"fieldname": "status_pajak",
			"label": _("STATUS PAJAK"),
			"fieldtype": "Data",
			"width": 200
		},
		{
			"fieldname": "area",
			"label": _("AREA"),
			"fieldtype": "Data",
			"width": 200
		},
		{
			"fieldname": "sub_area",
			"label": _("SUB AREA"),
			"fieldtype": "Data",
			"width": 200
		},
		{
			"fieldname": "bank",
			"label": _("BANK"),
			"fieldtype": "Data",
			"width": 200
		},
		{
			"fieldname": "kliring_bank",
			"label": _("KLIRING BANK"),
			"fieldtype": "Data",
			"width": 200
		},
		{
			"fieldname": "nama_tertera_pada_bank",
			"label": _("NAMA TERTERA PADA BANK"),
			"fieldtype": "Data",
			"width": 200
		},
		{
			"fieldname": "rekening_bank",
			"label": _("REKENING BANK"),
			"fieldtype": "Data",
			"width": 200
		},
		{
			"fieldname": "gaji_pokok",
			"label": _("Gaji Pokok"),
			"fieldtype": "Currency",
			"width": 200
		},
		{
			"fieldname": "uang_daerah",
			"label": _("Uang Daerah"),
			"fieldtype": "Currency",
			"width": 200
		},
		{
			"fieldname": "uang_perumahan",
			"label": _("Uang Perumahan"),
			"fieldtype": "Currency",
			"width": 200
		},
		{
			"fieldname": "uang_transport",
			"label": _("Uang Transport"),
			"fieldtype": "Currency",
			"width": 200
		},
		{
			"fieldname": "uang_makan",
			"label": _("Uang Makan"),
			"fieldtype": "Currency",
			"width": 200
		},
		{
			"fieldname": "premi_perawatan_kendaraan",
			"label": _("Premi Perawatan Kendaraan"),
			"fieldtype": "Currency",
			"width": 200
		},
		{
			"fieldname": "uang_telekomunikasi",
			"label": _("Uang Telekomunikasi"),
			"fieldtype": "Currency",
			"width": 200
		},
		{
			"fieldname": "uang_kehadiran",
			"label": _("Uang Kehadiran"),
			"fieldtype": "Currency",
			"width": 200
		},
		{
			"fieldname": "bpjs_kesehatan",
			"label": _("BPJS Kesehatan"),
			"fieldtype": "Currency",
			"width": 200
		},
		{
			"fieldname": "jht",
			"label": _("JHT"),
			"fieldtype": "Currency",
			"width": 200
		},
		{
			"fieldname": "jp",
			"label": _("JP"),
			"fieldtype": "Currency",
			"width": 200
		},
		{
			"fieldname": "angsuran_motor",
			"label": _("Angsuran Motor"),
			"fieldtype": "Currency",
			"width": 200
		},
		{
			"fieldname": "potongan_lainnya",
			"label": _("Potongan Lainnya"),
			"fieldtype": "Currency",
			"width": 200
		},
		{
			"fieldname": "jkk",
			"label": _("JKK"),
			"fieldtype": "Currency",
			"width": 200
		},
		{
			"fieldname": "bpjs_kesehatan_perusahaan",
			"label": _("BPJS Kesehatan Perusahaan"),
			"fieldtype": "Currency",
			"width": 200
		},
		{
			"fieldname": "jkm",
			"label": _("JKM"),
			"fieldtype": "Currency",
			"width": 200
		},
		{
			"fieldname": "jht_perusahaan",
			"label": _("JHT Perusahaan"),
			"fieldtype": "Currency",
			"width": 200
		},
		{
			"fieldname": "jp_perusahaan",
			"label": _("JP Perusahaan"),
			"fieldtype": "Currency",
			"width": 200
		},
		{
			"fieldname": "pph21",
			"label": _("PPh21"),
			"fieldtype": "Currency",
			"width": 200
		},
		{
			"fieldname": "tetap",
			"label": _("TETAP"),
			"fieldtype": "Currency",
			"width": 200
		},
		{
			"fieldname": "tidak_tetap",
			"label": _("TIDAK TETAP"),
			"fieldtype": "Currency",
			"width": 200
		},
		{
			"fieldname": "deduction",
			"label": _("DEDUCTION"),
			"fieldtype": "Currency",
			"width": 200
		},
		{
			"fieldname": "total",
			"label": _("TOTAL"),
			"fieldtype": "Currency",
			"width": 200
		},
	]

def get_data(filters):
  data = []
  conditions = get_condition(filters)
  
  query = frappe.db.sql("""
		SELECT 
				ss.name as slip_name,
				e.name as id_karyawan,
				e.employee_name as nama_karyawan,
				e.custom_religion as agama,
				e.date_of_joining as tanggal_masuk_kerja,
				e.pkp_status as status_pajak,
				c.abbr as area,
				e.unit as sub_area,
				e.nama_bank as bank,
				e.kliring_number as kliring_bank,
				e.employee_name as nama_tertera_pada_bank,
				e.bank_ac_no as rekening_bank,

				sd.gaji_pokok,
				sd.uang_daerah,
				sd.uang_perumahan,
				sd.uang_transport,
				sd.uang_makan,
				sd.premi_perawatan_kendaraan,
				sd.uang_telekomunikasi,
				sd.uang_kehadiran,
				sd.bpjs_kesehatan,
				sd.jht,
				sd.jp,
				ssll.angsuran_motor,
				ssll.potongan_lainnya,
				sd.jkk,
				sd.bpjs_kesehatan_perusahaan,
				sd.jkm,
				sd.jht_perusahaan,
				sd.jp_perusahaan,
				sd.pph21,
				
				sd.gaji_pokok as tetap,
				(
					COALESCE(sd.uang_daerah, 0) +
					COALESCE(sd.uang_perumahan, 0) +
					COALESCE(sd.uang_transport, 0) +
					COALESCE(sd.uang_makan, 0) +
					COALESCE(sd.premi_perawatan_kendaraan, 0) +
					COALESCE(sd.uang_telekomunikasi, 0) +
					COALESCE(sd.uang_kehadiran, 0)
			) as tidak_tetap,
				(
					COALESCE(sd.bpjs_kesehatan, 0) +
					COALESCE(sd.jht, 0) +
					COALESCE(sd.jp, 0) +
					COALESCE(ssll.angsuran_motor, 0) +
					COALESCE(ssll.potongan_lainnya, 0)
			) as deduction,
			(
					COALESCE(sd.gaji_pokok, 0)
					+
					(
							COALESCE(sd.uang_daerah, 0) +
							COALESCE(sd.uang_perumahan, 0) +
							COALESCE(sd.uang_transport, 0) +
							COALESCE(sd.uang_makan, 0) +
							COALESCE(sd.premi_perawatan_kendaraan, 0) +
							COALESCE(sd.uang_telekomunikasi, 0) +
							COALESCE(sd.uang_kehadiran, 0)
					)
					-
					(
							COALESCE(sd.bpjs_kesehatan, 0) +
							COALESCE(sd.jht, 0) +
							COALESCE(sd.jp, 0) +
							COALESCE(ssll.angsuran_motor, 0) +
							COALESCE(ssll.potongan_lainnya, 0)
					)
			) as total

		FROM `tabSalary Slip` ss

		LEFT JOIN (
				SELECT 
						sd.parent,

						SUM(
								CASE
										WHEN ss.salary_structure = 'NON STAFF SALARY STRUCTURE'
												AND sd.salary_component IN ('Gaji Pokok', 'HKnE')
										THEN sd.amount

										WHEN ss.salary_structure != 'NON STAFF SALARY STRUCTURE'
												AND sd.salary_component = 'Base Salary'
										THEN sd.amount

										ELSE 0
								END
						) as gaji_pokok,

						SUM(CASE WHEN sd.salary_component = 'Tunjangan Daerah' THEN sd.amount ELSE 0 END) as uang_daerah,
						SUM(CASE WHEN sd.salary_component = 'Tunjangan Perumahan' THEN sd.amount ELSE 0 END) as uang_perumahan,
						SUM(CASE WHEN sd.salary_component = 'Tunjangan Transportasi' THEN sd.amount ELSE 0 END) as uang_transport,
						SUM(CASE WHEN sd.salary_component = 'Tunjangan Makan' THEN sd.amount ELSE 0 END) as uang_makan,
						SUM(CASE WHEN sd.salary_component = 'Subsidi Perawatan Kendaraan' THEN sd.amount ELSE 0 END) as premi_perawatan_kendaraan,
						SUM(CASE WHEN sd.salary_component = 'Tunjangan Komunikasi' THEN sd.amount ELSE 0 END) as uang_telekomunikasi,
						SUM(CASE WHEN sd.salary_component = 'Premi Kehadiran' THEN sd.amount ELSE 0 END) as uang_kehadiran,
						SUM(CASE WHEN sd.salary_component = 'BPJS Kesehatan (Karyawan)' THEN sd.amount ELSE 0 END) as bpjs_kesehatan,
						SUM(CASE WHEN sd.salary_component LIKE '%%BPJS TK - JKK%%' THEN sd.amount ELSE 0 END) as jkk,
						SUM(CASE WHEN sd.salary_component = 'BPJS TK - JHT (Karyawan)' THEN sd.amount ELSE 0 END) as jht,
						SUM(CASE WHEN sd.salary_component = 'BPJS TK - JP (Karyawan)' THEN sd.amount ELSE 0 END) as jp,
						SUM(CASE WHEN sd.salary_component = 'BPJS Kesehatan (Perusahaan)' THEN sd.amount ELSE 0 END) as bpjs_kesehatan_perusahaan,
						SUM(CASE WHEN sd.salary_component = 'BPJS TK - JKM' THEN sd.amount ELSE 0 END) as jkm,
						SUM(CASE WHEN sd.salary_component = 'BPJS TK - JHT (Perusahaan)' THEN sd.amount ELSE 0 END) as jht_perusahaan,
						SUM(CASE WHEN sd.salary_component = 'BPJS TK - JP (Perusahaan)' THEN sd.amount ELSE 0 END) as jp_perusahaan,
						SUM(CASE WHEN sd.salary_component = 'PPH21 TER Gross Up' THEN sd.amount ELSE 0 END) as pph21

				FROM `tabSalary Detail` sd
				JOIN `tabSalary Slip` ss ON ss.name = sd.parent 

				GROUP BY sd.parent
		) sd ON sd.parent = ss.name

		LEFT JOIN (
				SELECT 
						ssll.parent,
						SUM(CASE WHEN lp.product_name = 'Subsidi Motor Karyawan' THEN ssll.total_payment ELSE 0 END) as angsuran_motor,
						SUM(CASE WHEN lp.product_name != 'Subsidi Motor Karyawan' THEN ssll.total_payment ELSE 0 END) as potongan_lainnya
				FROM `tabSalary Slip Loan` ssll
				JOIN `tabLoan` l ON l.name = ssll.loan
				JOIN `tabLoan Product` lp ON lp.name = l.loan_product
				GROUP BY ssll.parent
		) ssll ON ssll.parent = ss.name

		JOIN `tabEmployee` e ON e.name = ss.employee
		JOIN `tabCompany` c ON c.name = e.company
		WHERE e.grade != 'NON STAF' {};
  """.format(conditions), filters, as_dict=True)
  
  for row in query:
    data.append(row)
  
  return data

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

	if filters.get("bulan"):
		filters["month_num"] = bulan_map.get(filters.get("bulan"), 1)
		conditions += " AND MONTH(ss.posting_date) = %(month_num)s"

	if filters.get("tahun"):
		conditions += " AND YEAR(ss.posting_date) = %(tahun)s"

	if filters.get("employee"):
		conditions += " AND ss.employee = %(employee)s"

	return conditions