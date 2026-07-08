// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan List Bayar Harian"] = {
	"filters": [

	],
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname === "submit_button" && data.submit_button) {
			return `
					<button 
						class="btn btn-primary btn-xs submit-btn"
						data-docname="${data.submit_button}">
						Submit
					</button>
				`;
		}

		return value;
	},
	onload: function (report) {
		if (!document.getElementById("custom-report-style")) {
			const style = document.createElement("style");
			style.id = "custom-report-style";
			style.innerHTML = `
				.dt-row:has(.dt-cell__content[title="PINDAH DANA"]) .dt-cell {
					background-color: #0070c0!important;
					color: #fff!important;
				}
				.dt-row:has(.dt-cell__content[title="PINDAH DANA"]) .dt-cell a {
					color: #fff!important;
				}

				.dt-row:has(.dt-cell__content[title="BPJS KESEHATAN"]) .dt-cell {
					background-color: #fbe4d5!important;
					color: red!important;
				}
				.dt-row:has(.dt-cell__content[title="BPJS KESEHATAN"]) .dt-cell a {
					color: red!important;
				}
				.dt-row:has(.dt-cell__content[title="TOTAL BPJS KESEHATAN"]) .dt-cell {
					background-color: #c55a11!important;
					color: #fff !important;
				}

				.dt-row:has(.dt-cell__content[title="TOTAL TAGIHAN HRD"]) .dt-cell,
				.dt-row:has(.dt-cell__content[title="TOTAL TAGIHAN SUPPLIER"]) .dt-cell {
					background-color: #2e75b5!important;
					color: #fff !important;
				}

				.dt-row:has(.dt-cell__content[title="PINDAH DANA"]) .dt-cell:nth-child(1),
				.dt-row:has(.dt-cell__content[title="BPJS KESEHATAN"]) .dt-cell:nth-child(1),
				.dt-row:has(.dt-cell__content[title="TOTAL BPJS KESEHATAN"]) .dt-cell:nth-child(1),
				.dt-row:has(.dt-cell__content[title="TOTAL TAGIHAN HRD"]) .dt-cell:nth-child(1),
				.dt-row:has(.dt-cell__content[title="TOTAL TAGIHAN SUPPLIER"]) .dt-cell:nth-child(1) {
					background-color: unset!important;
					color: unset!important;
				}
			`;
			document.head.appendChild(style);
		}

		$(document).on("click", ".submit-btn", function (e) {
			let docname = $(this).data("docname");

			frappe.prompt(
				[
					{
						fieldname: "reference_no",
						label: "No Referensi",
						fieldtype: "Data",
						reqd: 1
					},
					{
						fieldname: "reference_date",
						label: "Tanggal Bayar",
						fieldtype: "Date",
						reqd: 1,
						default: frappe.datetime.get_today()
					}
				],
				function (values) {
					frappe.call({
						method: "sth.api.submit_payment_entry",
						args: {
							docname: docname,
							reference_no: values.reference_no,
							reference_date: values.reference_date
						},
						callback: function () {
							frappe.show_alert({
								message: __("Berhasil submit {0} Payment Entry", [selected_names.length]),
								indicator: "green"
							});

							frappe.query_report.refresh();
						}
					});
				},
				"Input Pembayaran",
				"Submit"
			);
		});

		report.page.add_inner_button(__("Submit Selected"), function () {
			let selected_names = [];

			$(".payment-row:checked").each(function () {
				selected_names.push($(this).data("name"));
			});

			if (!selected_names.length) {
				frappe.msgprint("Pilih data terlebih dahulu");
				return;
			}

			frappe.prompt(
				[
					{
						fieldname: "reference_no",
						label: "No Referensi",
						fieldtype: "Data",
						reqd: 1
					},
					{
						fieldname: "reference_date",
						label: "Tanggal Bayar",
						fieldtype: "Date",
						reqd: 1,
						default: frappe.datetime.get_today()
					}
				],
				function (values) {
					frappe.call({
						method: "sth.api.submit_payment_entry",
						args: {
							docname: selected_names,
							reference_no: values.reference_no,
							reference_date: values.reference_date
						},
						callback: function () {
							frappe.show_alert({
								message: __("Berhasil submit {0} Payment Entry", [selected_names.length]),
								indicator: "green"
							});

							frappe.query_report.refresh();
						}
					});
				},
				"Input Pembayaran",
				"Submit"
			);
		});
	}
};
