// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt
const jenisTransaksi = ["Seluruhnya", "Mutasi Dalam Perjalanan", "Penerimaan", "Pengembalian Pengeluaran", "Penerimaan Mutasi", "Adjustment Masuk", "Pengeluaran", "Pengeluaran Alokasi", "Pengembalian Penerimaan", "Pengeluaran Mutasi", "Adjustment Keluar"];

frappe.query_reports["Laporan Transaksi Gudang"] = {
	"filters": [
		{
			fieldname: "company",
			label: __("Perusahaan"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1
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
			fieldname: "tipe_transaksi",
			label: __("Tipe Transaksi"),
			fieldtype: "Autocomplete",
			options: jenisTransaksi.join("\n"),
		},
		{
			fieldname: "item_code",
			label: __("Kode Barang"),
			fieldtype: "Link",
			options: "Item"
		},
	]
};
