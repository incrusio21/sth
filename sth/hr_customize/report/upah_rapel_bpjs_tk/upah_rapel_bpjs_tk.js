// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Upah Rapel BPJS TK"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company"),
			"reqd": 1,
		},
		// {
		// 	"fieldname": "from_date",
		// 	"label": __("From Date"),
		// 	"fieldtype": "Date",
		// },
		// {
		// 	"fieldname": "to_date",
		// 	"label": __("To Date"),
		// 	"fieldtype": "Date",
		// },
		{
			"fieldname": "employee_grade",
			"label": __("Employee Grade"),
			"fieldtype": "Link",
			"options": "Employee Grade",
		},
		{
			"fieldname": "employment_type",
			"label": __("Employment Type"),
			"fieldtype": "Link",
			"options": "Employment Type",
		},
	]
};
