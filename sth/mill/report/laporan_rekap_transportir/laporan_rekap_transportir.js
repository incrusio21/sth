// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan Rekap Transportir"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_default("company"),
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
					},
				};
			},
		},
		{
			"fieldname": "no_kontrak",
			"label": __("No Kontrak"),
			"fieldtype": "Link",
			"options": "Sales Order",
		},
		{
			"fieldname": "no_do",
			"label": __("No DO"),
			"fieldtype": "Link",
			"options": "Delivery Order",
		},
		{
			"fieldname": "no_polisi",
			"label": __("No Polisi"),
			"fieldtype": "Data",
		},
		{
			"fieldname": "transportir",
			"label": __("Transportir"),
			"fieldtype": "Link",
			"options": "Customer",
		},
		{
			"fieldname": "produk",
			"label": __("Produk"),
			"fieldtype": "Link",
			"options": "Item",
		},
		{
			"fieldname": "from_date",
			"label": __("Tanggal Dari"),
			"fieldtype": "Date",
			"default": frappe.datetime.month_start(),
			"reqd": 0
		},
		{
			"fieldname": "to_date",
			"label": __("Tanggal Sampai"),
			"fieldtype": "Date",
			"default": frappe.datetime.month_end(),
			"reqd": 0
		},
	]
};
