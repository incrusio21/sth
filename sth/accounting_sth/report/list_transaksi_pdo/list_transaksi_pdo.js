// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["List transaksi PDO"] = {
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
	]
};
