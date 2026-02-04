// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan Rekap Daftar Karyawan"] = {
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
			"fieldname": "status_level",
			"label": __("Status/Level"),
			"fieldtype": "Link",
			"options": "Employment Type",
		},
	]
};
