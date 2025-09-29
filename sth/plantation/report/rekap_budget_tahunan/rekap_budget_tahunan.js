// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Rekap Budget Tahunan"] = {
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
			// "default": "All",
			// "reqd": 1
		},
		{
			"fieldname": "divisi",
			"label": __("Divisi"),
			"fieldtype": "Link",
			"options": "Divisi",
			// "default": "All",
			// "reqd": 1
		},
		{
			"fieldname": "kegiatan",
			"label": __("Kegiatan"),
			"fieldtype": "Link",
			"options": "Kegiatan",
			// "default": "All",
			// "reqd": 1
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
		const month_fields = [
			"jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"
		];

		if (column.fieldname === "amount" || month_fields.includes(column.fieldname) || column.fieldname === "rp_per_sat") {
			if (!value || value === 0) {
				return ""; // kosong
			}
		}
		return default_formatter(value, row, column, data);
	}
};
