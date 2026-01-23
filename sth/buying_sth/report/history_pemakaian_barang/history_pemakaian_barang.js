// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

let months = [
	"Januari", "Februari", "Maret", "April", "Mei", "Juni",
	"Juli", "Agustus", "September", "Oktober", "November", "Desember"
];

let stringMonths = months.join("\n")

frappe.query_reports["History Pemakaian Barang"] = {
	"filters": [
		// {
		// 	fieldname: "company",
		// 	label: __("Company"),
		// 	fieldtype: "Link",
		// 	options: "Company",
		// 	default: frappe.defaults.get_default("company"),
		// },
		{
			fieldname: "vehicle_code",
			label: __("Kode Kendaraan"),
			fieldtype: "Link",
			options: "Alat Berat Dan Kendaraan",
		},
		{
			fieldname: "driver",
			label: __("Nama Sopir"),
			fieldtype: "Link",
			options: "Employee",
		},
		{
			fieldname: "year",
			label: __("Tahun"),
			fieldtype: "Link",
			options: "Fiscal Year",
			default: new Date().getFullYear(),
			reqd: 1
		},
		{
			fieldname: "from_month",
			label: __("Dari Bulan"),
			fieldtype: "Autocomplete",
			options: stringMonths,
			default: months[new Date().getMonth() - 3],
			reqd: 1
		},
		{
			fieldname: "to_month",
			label: __("Sampai Bulan"),
			fieldtype: "Autocomplete",
			options: stringMonths,
			default: months[new Date().getMonth()],
			reqd: 1
		},
	]
};
