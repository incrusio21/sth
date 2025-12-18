// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan Daftar Izin Cuti"] = {
	"filters": [
		{
			"fieldname": "jenis_izin_cuti",
			"label": __("Jenis Izin Cuti"),
			"fieldtype": "Link",
			"options": "Leave Type",
		},
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
			"fieldname": "level",
			"label": __("Level"),
			"fieldtype": "Link",
			"options": "Employment Type",
		},
	]
};
