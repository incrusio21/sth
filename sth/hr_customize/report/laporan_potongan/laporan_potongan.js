// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

let months = [
	"Januari", "Februari", "Maret", "April", "Mei", "Juni",
	"Juli", "Agustus", "September", "Oktober", "November", "Desember"
];

let stringMonths = months.join("\n")

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
			fieldname: "periode_bulan",
			label: __("Periode Bulan"),
			fieldtype: "Autocomplete",
			options: stringMonths,
		},
	]
};
