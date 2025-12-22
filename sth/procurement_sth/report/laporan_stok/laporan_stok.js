// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan Stok"] = {
	"filters": [
		{
			fieldname: "company",
			label: __("Perusahaan"),
			fieldtype: "Link",
			options: "Company"
		},
		{
			fieldname: "unit",
			label: __("Unit"),
			fieldtype: "Link",
			options: "Unit",
			get_query: () => {
				let company = frappe.query_report.get_filter_value("company");
				return {
					filters: {
						...(company && { company }),
					},
				};
			},
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "item_group",
			label: __("Kelompok Barang"),
			fieldtype: "Link",
			options: "Item Group"
		},
		{
			fieldname: "item_code",
			label: __("Nama Barang"),
			fieldtype: "Link",
			options: "Item"
		},
		{
			fieldname: "gudang",
			label: __("Gudang"),
			fieldtype: "Link",
			options: "Warehouse",
			get_query: () => {
				let company = frappe.query_report.get_filter_value("company");
				return {
					filters: {
						is_group: 0,
						...(company && { company })
					},
				};
			}
		},
	]
};
