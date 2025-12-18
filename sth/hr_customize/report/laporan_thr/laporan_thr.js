// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan THR"] = {
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
			"fieldname": "tahun",
			"label": __("Tahun"),
			"fieldtype": "Link",
			"options": "Fiscal Year",
		},
	]
};
