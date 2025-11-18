// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Rekap Budget Panen"] = {
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
		if (column.fieldname != "divisi" && column.fieldname != "blok" && column.fieldname != "tahun_tanam") {
			let num = parseFloat(value) || 0;

			let formatted = num.toLocaleString('id-ID', {
				minimumFractionDigits: 0,
				maximumFractionDigits: 0
			});

			formatted = formatted.replace(/\./g, ',');
			return formatted;
		}

		return default_formatter(value, row, column, data);
	}
};
