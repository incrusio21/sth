// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Rekap Kegiatan Panen"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company"),
			"reqd": 1
		},
		{
			"fieldname": "unit",
			"label": __("Unit"),
			"fieldtype": "Link",
			"options": "Unit",
		},
		{
			"fieldname": "divisi",
			"label": __("Divisi"),
			"fieldtype": "Link",
			"options": "Divisi",
		},
		{
			"fieldname": "periode",
			"label": __("Periode/Tahun"),
			"fieldtype": "Link",
			"options": "Fiscal Year",
			"default": frappe.datetime.now_date().split("-")[0],
			"reqd": 1,
		}
	],
	formatter: function (value, row, column, data, default_formatter) {
		if (column.fieldname === "budget" || column.fieldname === "cost_sat") {
			if (!value || value === 0) {
				return ""; // kosong
			}
		}

		// if (column.fieldname == "cost_sat") {
		// 	value = `<div style="text-align: right">${value}</div>`;
		// }

		return default_formatter(value, row, column, data);
	}
};
