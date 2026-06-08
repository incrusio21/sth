// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Monthly Progress Report"] = {
	"filters": [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_default("company"),
		},
		{
			fieldname: "unit",
			label: __("Unit"),
			fieldtype: "Link",
			options: "Unit",
			get_query: function () {
				let company = frappe.query_report.get_filter_value("company");

				return {
					filters: {
						company: company,
						mill: 1,
					},
				};
			},
		},
		{
			fieldname: "periode",
			label: __("Periode"),
			fieldtype: "Link",
			options: "Fiscal Year",
			reqd: 1,
		},
		{
			fieldname: "from_month",
			label: __("From Month"),
			fieldtype: "Select",
			reqd: 1,
			options: [
				"Jan",
				"Feb",
				"Mar",
				"Apr",
				"May",
				"Jun",
				"Jul",
				"Aug",
				"Sep",
				"Oct",
				"Nov",
				"Dec"
			],
		},
		{
			fieldname: "to_month",
			label: __("To Month"),
			fieldtype: "Select",
			reqd: 1,
			options: [
				"Jan",
				"Feb",
				"Mar",
				"Apr",
				"May",
				"Jun",
				"Jul",
				"Aug",
				"Sep",
				"Oct",
				"Nov",
				"Dec"
			],
		},
	]
};
