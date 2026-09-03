// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

const JENIS_COSTING = ["Costing Bengkel", "Costing Mill", "Costing Panen", "Costing Perawatan"];

frappe.query_reports["Jurnal Costing"] = {
	filters: [
		{
			fieldname: "accounting_period",
			label: __("Accounting Period"),
			fieldtype: "Link",
			options: "Accounting Period",
			reqd: 1,
			on_change(report) {
				isi_dari_accounting_period(report);
			},
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			read_only: 1,
		},
		{
			fieldname: "unit",
			label: __("Unit"),
			fieldtype: "Link",
			options: "Unit",
			read_only: 1,
		},
		{
			fieldname: "from_date",
			label: __("Periode Dari"),
			fieldtype: "Date",
			read_only: 1,
		},
		{
			fieldname: "to_date",
			label: __("Periode Sampai"),
			fieldtype: "Date",
			read_only: 1,
		},
		{
			fieldname: "jenis_costing",
			label: __("Jenis Costing"),
			fieldtype: "MultiSelectList",
			get_data(txt) {
				return JENIS_COSTING.filter((jenis) =>
					!txt || jenis.toLowerCase().includes(txt.toLowerCase())
				).map((jenis) => ({ value: jenis, description: "" }));
			},
		},
		{
			fieldname: "account",
			label: __("Akun"),
			fieldtype: "MultiSelectList",
			get_data(txt) {
				return frappe.db.get_link_options("Account", txt, {
					company: frappe.query_report.get_filter_value("company"),
				});
			},
		},
		{
			fieldname: "cost_center",
			label: __("Cost Center"),
			fieldtype: "MultiSelectList",
			get_data(txt) {
				return frappe.db.get_link_options("Cost Center", txt, {
					company: frappe.query_report.get_filter_value("company"),
				});
			},
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (data && data.is_total) {
			value = `<span style="font-weight: 600">${value}</span>`;
		}

		return value;
	},

	onload(report) {
		isi_dari_accounting_period(report);
	},
};

// Company, unit dan rentang tanggal cuma tampilan — yang dipakai server tetap
// Accounting Period-nya, jadi tiga filter itu selalu ikut periode yang dipilih.
function isi_dari_accounting_period(report) {
	const accounting_period = frappe.query_report.get_filter_value("accounting_period");

	if (!accounting_period) {
		frappe.query_report.set_filter_value("company", "");
		frappe.query_report.set_filter_value("unit", "");
		frappe.query_report.set_filter_value("from_date", "");
		frappe.query_report.set_filter_value("to_date", "");
		report.page.clear_indicator();
		return;
	}

	frappe.db
		.get_value("Accounting Period", accounting_period, ["company", "unit", "start_date", "end_date"])
		.then(({ message }) => {
			if (!message) return;
			frappe.query_report.set_filter_value("company", message.company || "");
			frappe.query_report.set_filter_value("unit", message.unit || "");
			frappe.query_report.set_filter_value("from_date", message.start_date || "");
			frappe.query_report.set_filter_value("to_date", message.end_date || "");
			report.page.set_indicator(__("Periode: {0}", [accounting_period]), "blue");
		});
}
