// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan Angsuran Karwayan"] = {
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
			"fieldname": "nama_karyawan",
			"label": __("Nama Karyawan"),
			"fieldtype": "Link",
			"options": "Employee",
		},
		{
			"fieldname": "unit",
			"label": __("Unit"),
			"fieldtype": "Link",
			"options": "Unit",
		},
		{
			"fieldname": "company",
			"label": __("PT"),
			"fieldtype": "Link",
			"options": "Company",
		},
		{
			"fieldname": "jenis_angsuran",
			"label": __("Jenis Angsuran"),
			"fieldtype": "Link",
			"options": "Loan Product",
		},
		{
			"fieldname": "status",
			"label": __("Status"),
			"fieldtype": "Select",
			"options": [
				"Draft",
				"Sanctioned",
				"Partially Disbursed",
				"Disbursed",
				"Active",
				"Loan Closure Requested",
				"Closed",
				"Written Off",
				"Settled",
			],
		},
	]
};
