// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan Equalisasi Pajak"] = {
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
			"fieldname": "jenis_pajak",
			"label": __("Jenis Pajak"),
			"fieldtype": "Link",
			"options": "Tax Rate",
			get_query: () => {
				return {
					filters: {
						is_group: 1
					}
				};
			}
		},
		{
			"fieldname": "from_date",
			"label": __("Tanggal Dari"),
			"fieldtype": "Date",
			"reqd": 0
		},
		{
			"fieldname": "to_date",
			"label": __("Tanggal Sampai"),
			"fieldtype": "Date",
			"reqd": 0
		},
	]
};
