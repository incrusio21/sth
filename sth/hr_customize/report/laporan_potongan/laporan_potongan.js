// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt
frappe.query_reports["Laporan Potongan"] = {
	"filters": [
		{
			"fieldname": "no_transaksi",
			"label": __("No Transaksi"),
			"fieldtype": "Link",
			"options": "Employee Potongan",
		},
		{
			"fieldname": "tahun",
			"label": __("Tahun"),
			"fieldtype": "Link",
			"options": "Fiscal Year",
		},
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
			"fieldname": "potongan",
			"label": __("Potongan"),
			"fieldtype": "Link",
			"options": "Jenis Potongan",
		},
		{
			"fieldname": "bulan",
			"label": __("Bulan"),
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
	]
};
