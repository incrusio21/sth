// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan BPJS"] = {
	"filters": [
		{
			"fieldname": "kode",
			"label": __("Kode"),
			"fieldtype": "Link",
			"options": "Set Up BPJS PT",
		},
		{
			"fieldname": "company",
			"label": __("Company"),
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
			"fieldname": "bpjs_type",
			"label": __("Jenis BPJS"),
			"fieldtype": "Select",
			"options": ["BPJS KES", "BPJS TK"],
		},
		{
			"fieldname": "start_periode",
			"label": __("Start Periode"),
			"fieldtype": "Date",
		},
		{
			"fieldname": "end_periode",
			"label": __("End Periode"),
			"fieldtype": "Date",
		},
	]
};
