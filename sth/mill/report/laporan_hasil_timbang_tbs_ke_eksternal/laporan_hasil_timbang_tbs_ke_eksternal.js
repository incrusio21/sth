// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan Hasil Timbang TBS Ke Eksternal"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_default("company"),
		},
		{
			fieldname: "unit",
			label: __("Unit"),
			fieldtype: "Link",
			options: "Unit",
			get_query: function () {
				let company = frappe.query_report.get_filter_value("company");

				return {
					filters: {
						company: company,
					},
				};
			},
		},
		{
			"fieldname": "ticket_number",
			"label": __("Ticket Number"),
			"fieldtype": "Link",
			"options": "Security Check Point",
		},
		{
			"fieldname": "spb",
			"label": __("SPB"),
			"fieldtype": "Link",
			"options": "Surat Pengantar Buah",
		},
		{
			"fieldname": "no_kontrak",
			"label": __("No Kontrak"),
			"fieldtype": "Link",
			"options": "Delivery Order",
		},
		{
			"fieldname": "customer",
			"label": __("Customer"),
			"fieldtype": "Link",
			"options": "Customer",
		},
		{
			"fieldname": "driver",
			"label": __("Driver"),
			"fieldtype": "Data",
		},
		{
			"fieldname": "no_polisi",
			"label": __("No Polisi"),
			"fieldtype": "Data",
		},
	],
	"formatter": function (value, row, column, data, default_formatter) {
		const float_cols = [
			"internal_berat_masuk", "internal_berat_keluar", "internal_berat_bersih",
			"internal_janjang", "external_berat_masuk", "external_berat_keluar",
			"external_berat_bersih", "external_potongan", "external_berat_normal",
			"berat_pengakuan_jual", "varian_kg", "denda_kg", "denda_harga_tbs",
		];

		if (column.fieldname && float_cols.includes(column.fieldname) && value !== null && value !== "") {
			return format_number(value, null, 0);
		}

		return default_formatter(value, row, column, data);
	},
};
