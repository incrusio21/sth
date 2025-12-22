// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan Stock Opname Aset"] = {
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
			"fieldname": "status",
			"label": __("Status"),
			"fieldtype": "Select",
			"options": ["Draft", "Submitted", "Partially Depreciated", "Fully Depreciated", "Sold", "Scrapped", "In Maintenance", "Out of Order", "Issue", "Receipt", "Capitalized", "Work In Progress"],
		},
	]
};
