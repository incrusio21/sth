// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan Pengajuan Klaim Karyawan"] = {
	"filters": [
		{
			"fieldname": "pt",
			"label": __("PT"),
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
			"fieldname": "golongan",
			"label": __("Golongan"),
			"fieldtype": "Link",
			"options": "Employee Grade",
		},
		{
			"fieldname": "jabatan",
			"label": __("Jabatan"),
			"fieldtype": "Link",
			"options": "Designation",
		},
		{
			"fieldname": "jenis_klaim",
			"label": __("Jenis Klaim"),
			"fieldtype": "Link",
			"options": "Expense Claim Type",
		},
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
		},
	]
};
