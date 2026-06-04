// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan Histori Stok"] = {
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
			fieldname: "from_date",
			label: __("Dari Tanggal"),
			fieldtype: "Date",
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("Ke Tanggal"),
			fieldtype: "Date",
			reqd: 1,
		},
		{
			fieldname: "item_code",
			label: __("Kode Barang"),
			fieldtype: "Link",
			options: "Item",
			reqd: 1,
		},
	],
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname === "in_qty" && data.in_qty) {
			let qty = Math.abs(data.in_qty);
			value = `
				<span style="color:green; font-weight:bold;">
					${format_number(qty)}
				</span>
			`;
		}

		if (column.fieldname === "out_qty" && data.out_qty) {
			let qty = Math.abs(data.out_qty);
			value = `
				<span style="color:red; font-weight:bold;">
					-${format_number(qty)}
				</span>
			`;
		}

		return value;
	},
};
