// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Rekap Kegiatan Traksi"] = {
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
			"fieldname": "kode_kendaraan",
			"label": __("Kode Kendaraan"),
			"fieldtype": "Link",
			"options": "Alat Berat Dan Kendaraan",
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
			"upah_dan_premi", "bbm", "suku_cadang", "service", "lain_lain", "total", "rp_sat"
		];

		if (columns_default_blank.includes(column.fieldname)) {
			if (!value || value === 0) {
				return ""; // kosong
			}
		}
		return default_formatter(value, row, column, data);
	}
};
