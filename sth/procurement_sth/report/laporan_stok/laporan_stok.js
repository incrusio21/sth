// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan Stok"] = {
	"filters": [
		{
			fieldname: "company",
			label: __("Perusahaan"),
			fieldtype: "Link",
			options: "Company",
			reqd: 1,
			default: frappe.defaults.get_default("Company"),
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
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			reqd: 1,
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
	],
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname == "nama_barang" && data) {
			let filters = frappe.query_report.get_values();

			value = `
				<a 
					href="/app/query-report/Laporan%20Histori%20Stok?company=${encodeURIComponent(filters.company)}&from_date=${filters.from_date}&to_date=${filters.to_date}&item_code=${encodeURIComponent(data.kode_barang)}"
					target="_blank"
				>
					${data.nama_barang}
				</a>
			`;
		}
		return value;
	},
};
