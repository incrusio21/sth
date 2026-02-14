// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan Daftar Karyawan"] = {
	"filters": [
		{
			"fieldname": "pt",
			"label": __("PT"),
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
			"fieldname": "golongan",
			"label": __("Golongan"),
			"fieldtype": "Link",
			"options": "Employee Grade",
		},
		{
			"fieldname": "status_level",
			"label": __("Status/Level"),
			"fieldtype": "Link",
			"options": "Employment Type",
		},
		{
			"fieldname": "divisi",
			"label": __("Divisi"),
			"fieldtype": "Link",
			"options": "Divisi",
		},
		{
			"fieldname": "jabatan",
			"label": __("Jabatan"),
			"fieldtype": "Link",
			"options": "Designation",
		},
		{
			"fieldname": "status_karyawan",
			"label": __("Status Karyawan"),
			"fieldtype": "Select",
			"options": ["", "Active", "Inactive", "Suspended", "Left",],
		},
	],
	// formatter: function (value, row, column, data, default_formatter) {
	// 	value = default_formatter(value, row, column, data);

	// 	if (column.fieldname === "pas_foto") {
	// 		value = `<img src="${value}"/>`;
	// 	}

	// 	return value;
	// }
};
