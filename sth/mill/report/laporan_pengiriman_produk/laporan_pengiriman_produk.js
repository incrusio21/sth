// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan Pengiriman Produk"] = {
	"filters": [
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
			"fieldname": "no_kontrak",
			"label": __("No Kontrak"),
			"fieldtype": "Link",
			"options": "Sales Order"
		},
		{
			"fieldname": "no_do",
			"label": __("No DO"),
			"fieldtype": "Link",
			"options": "Delivery Order"
		},
		{
			"fieldname": "produk",
			"label": __("Produk"),
			"fieldtype": "Data",
		},
		{
			"fieldname": "transportir",
			"label": __("Transportir"),
			"fieldtype": "Data",
		},
		{
			"fieldname": "from_date",
			"label": __("Tanggal Dari"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 0
		},
		{
			"fieldname": "to_date",
			"label": __("Tanggal Sampai"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 0
		},
	]
};
