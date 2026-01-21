// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan Usia Stok"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
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
			label: __("Dari Tanggal"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			reqd: 1,
		},

		{
			fieldname: "to_date",
			label: __("Sampai Tanggal"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},

		{
			fieldname: "harga",
			label: __("Harga"),
			fieldtype: "Currency",
			default: 0
		},

		{
			fieldname: "kelompok_barang",
			label: __("Kelompok Barang"),
			fieldtype: "Link",
			options: "Item Group",
			get_query: () => {
				return {
					filters: {
						is_group: 1,
					},
				};
			},
		},

		{
			fieldname: "nama_barang",
			label: __("Nama Barang"),
			fieldtype: "Data",
		},

		{
			fieldname: "warehouse",
			label: __("Warehouse"),
			fieldtype: "Link",
			options: "Warehouse",
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
			fieldname: "sub_kelompok_barang",
			label: __("Sub Kelompok Barang"),
			fieldtype: "Link",
			options: "Item Group",
			get_query: () => {
				let parent_item_group = frappe.query_report.get_filter_value("kelompok_barang");
				return {
					filters: {
						is_group: 0,
						...(parent_item_group && { parent_item_group })
					},
				};
			},
		},

	],
};
