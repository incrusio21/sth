// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan Bukti Pemotongan Bulanan Pegawai Tetap"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
		},
		{
			"fieldname": "unit",
			"label": __("Unit"),
			"fieldtype": "Link",
			"options": "Unit",
		},
		{
			"fieldname": "grade",
			"label": __("Golongan"),
			"fieldtype": "Link",
			"options": "Employee Grade",
		},
		{
			"fieldname": "employment_type",
			"label": __("Tipe Karyawan"),
			"fieldtype": "Link",
			"options": "Employment Type",
		},
		{
			"fieldname": "designation",
			"label": __("Jabatan"),
			"fieldtype": "Link",
			"options": "Designation",
		},
		{
			"fieldname": "bulan",
			"label": __("Bulan"),
			"fieldtype": "Select",
			"options": [
				"Januari",
				"Februari",
				"Maret",
				"April",
				"Mei",
				"Juni",
				"Juli",
				"Agustus",
				"September",
				"Oktober",
				"November",
				"Desember"
			],
		},
		{
			"fieldname": "tahun",
			"label": __("Tahun"),
			"fieldtype": "Link",
			"options": "Fiscal Year",
		},
	]
};
