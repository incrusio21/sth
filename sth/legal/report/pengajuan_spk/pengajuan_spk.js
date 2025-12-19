// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Pengajuan SPK"] = {
	"filters": [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "unit",
			label: __("Unit"),
			fieldtype: "Link",
			options: "Unit",
			get_data: function (txt) {
				return frappe.db.get_link_options("Unit", txt, {
					company: frappe.query_report.get_filter_value("company"),
				});
			},
		},
		{
			fieldname: "supplier",
			label: __("Supplier"),
			fieldtype: "Link",
			options: "Supplier",
		},
		{
			fieldname: "project",
			label: __("Number"),
			fieldtype: "Link",
			options: "Project",
		},
		{
			fieldname: "project",
			label: __("Project Name"),
			fieldtype: "Data",
		},
	]
};
