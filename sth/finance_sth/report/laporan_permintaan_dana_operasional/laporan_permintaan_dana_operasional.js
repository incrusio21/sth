// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan Permintaan Dana Operasional"] = {
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
		{
			"fieldname": "year",
			"label": __("Tahun"),
			"fieldtype": "Link",
			"options": "Fiscal Year",
		},
		{
			"fieldname": "from_month",
			"label": __("Bulan Awal"),
			"fieldtype": "Select",
			"options": [
				"",
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
			"fieldname": "to_month",
			"label": __("Bulan Akhir"),
			"fieldtype": "Select",
			"options": [
				"",
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
		// {
		// 	fieldname: "from_date",
		// 	label: __("From Date"),
		// 	fieldtype: "Date",
		// 	reqd: 1,
		// 	default: frappe.datetime.add_months(
		// 		frappe.datetime.month_start(frappe.datetime.get_today()),
		// 		-1
		// 	)
		// },
		// {
		// 	fieldname: "to_date",
		// 	label: __("To Date"),
		// 	fieldtype: "Date",
		// 	reqd: 1,
		// 	default: frappe.datetime.month_start(frappe.datetime.get_today())
		// }
	],
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (data && data.is_header) {
			value = `<b>${value}</b>`;
		}

		return value;
	}
};
