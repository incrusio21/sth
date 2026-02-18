// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan Harian Kas dan Bank"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"reqd": 1,
			"default": frappe.defaults.get_default("company")
		},
		{
			"fieldname": "unit",
			"label": __("Unit"),
			"fieldtype": "Link",
			"options": "Unit",
			"get_query": function() {
				let company = frappe.query_report.get_filter_value("company");
				return {
					filters: {
						"company": company
					}
				};
			}
		},
		{
			"fieldname": "kas_bank",
			"label": __("Kas/Bank"),
			"fieldtype": "Select",
			"options": ["Kas", "Bank"],
		},
		{
			"fieldname": "from_date",
			"label": __("Dari"),
			"fieldtype": "Date"
		},
		{
			"fieldname": "to_date",
			"label": __("Sampai"),
			"fieldtype": "Date"
		},
	]
};
