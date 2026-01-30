// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan THR Detail"] = {
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
			"fieldname": "thr",
			"label": __("THR"),
			"fieldtype": "Link",
			"options": "Religion Group",
		},
		{
			"fieldname": "grade",
			"label": __("Grade"),
			"fieldtype": "Link",
			"options": "Employee Grade",
		},
		{
			"fieldname": "employment_type",
			"label": __("Employment Type"),
			"fieldtype": "Link",
			"options": "Employment Type",
		},
		{
			"fieldname": "start_periode",
			"label": __("Start Periode"),
			"fieldtype": "Date",
		},
		{
			"fieldname": "end_periode",
			"label": __("End Periode"),
			"fieldtype": "Date",
		},
		{
			"fieldname": "tahun",
			"label": __("Tahun"),
			"fieldtype": "Link",
			"options": "Fiscal Year",
		},
	]
};
