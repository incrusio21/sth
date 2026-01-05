// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan Gaji Kebun"] = {
	"filters": [
		{
			"fieldname": "unit",
			"label": __("Unit"),
			"fieldtype": "Link",
			"options": "Unit",
		},
	]
};
