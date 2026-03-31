// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan Histori Pemenuhan Kontrak"] = {
	"filters": [
		{
			"fieldname": "no_kontrak",
			"label": __("No Kontrak"),
			"fieldtype": "Link",
			"options": "Sales Order",
			"reqd": 1
		},
	]
};
