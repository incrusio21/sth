// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan Surat Peringatan"] = {
	"filters": [
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
		},
		{
			"fieldname": "unit",
			"label": __("Unit"),
			"fieldtype": "Link",
			"options": "Unit",
		},
		{
			"fieldname": "jenis_sp",
			"label": __("Jenis SP"),
			"fieldtype": "Link",
			"options": "Grievance Type",
		},
		{
			"fieldname": "tipe_karyawan",
			"label": __("Tipe Karyawan"),
			"fieldtype": "Link",
			"options": "Employee Grade",
		},
	]
};
