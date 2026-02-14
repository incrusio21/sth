// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan Perjalanan Dinas"] = {
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
			"fieldname": "jenis_pjd",
			"label": __("Jenis PJD"),
			"fieldtype": "Link",
			"options": "Purpose of Travel",
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
