// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan Deposito"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
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
		{
			"fieldname": "tahun",
			"label": __("Tahun"),
			"fieldtype": "Link",
			"options": "Fiscal Year",
		},
		{
			"fieldname": "jenis_deposito",
			"label": __("Jenis Deposito"),
			"fieldtype": "Select",
			"options": [
				"",
				"Non Roll Over",
				"Roll Over Pokok",
				"Roll Over Pokok + Bunga",
			],
		},
		{
			"fieldname": "status_deposito",
			"label": __("Status Deposito"),
			"fieldtype": "Select",
			"options": [
				"",
				"Belum",
				"Sudah",
				"Roll Overed"
			],
		},
		{
			"fieldname": "from_date",
			"label": __("Dari"),
			"fieldtype": "Date"
		},
		{
			"fieldname": "to_date",
			"label": __("Sampai"),
			"fieldtype": "Date"
		},
	]
};
