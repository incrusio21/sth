// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan Riwayat Purchase Request"] = {
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
			fieldname: "document_no",
			label: __("No Dokument"),
			fieldtype: "Link",
			options: "Material Request"
		},
		{
			fieldname: "purchase_order",
			label: __("Purchase Order"),
			fieldtype: "Link",
			options: "Purchase Order"
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
			fieldname: "item_code",
			label: __("Nama Barang"),
			fieldtype: "Link",
			options: "Item"
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Data",
		},
	]
};
