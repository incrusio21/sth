// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan Histori Aktual PDO"] = {
	"filters": [
		{
			"fieldname": "row_id",
			"label": __("Row ID"),
			"fieldtype": "Data",
		},
		{
			"fieldname": "type",
			"label": __("Type"),
			"fieldtype": "Select",
			"options": [
				"Bahan Bakar",
				"Perjalanan Dinas",
				"Kas",
				"Dana Cadangan",
				"Non PDO",
			],
		},
	]
};
