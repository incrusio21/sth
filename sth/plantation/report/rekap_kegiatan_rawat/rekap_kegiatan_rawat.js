// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Rekap Kegiatan Rawat"] = {
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
			"fieldname": "kegiatan",
			"label": __("Kegiatan"),
			"fieldtype": "Link",
			"options": "Kegiatan",
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
		const columns_default_blank = [
			"no_kegiatan", "budget", "volume", "cost_sat"
		];

		if (columns_default_blank.includes(column.fieldname)) {
			if (!value || value === 0) {
				return ""; // kosong
			}
		}

		if (column.fieldname == "no_kegiatan") {
			value = `<div style="text-align: left">${value}</div>`;
		} else if (column.fieldname == "volume") {
			value = `<div style="text-align: right">${value}</div>`;
		} else if (column.fieldname == "nama_kegiatan") {
			if (!row[3].content && !row[4].content) {
				value = `<div style="font-weight: bold">${value}</div>`;
			} else {
				value = `<div>${value}</div>`;
			}
		}

		return default_formatter(value, row, column, data);
	}
};
