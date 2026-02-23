// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan List Bayar Harian"] = {
	"filters": [

	],
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname === "submit_button") {

			// hanya tampilkan button jika payment_status ada value
			if (data.payment_status) {
				return `
					<button 
						class="btn btn-primary btn-sm submit-btn"
						data-docname="${data.submit_button}">
						Submit
					</button>
				`;
			} else {
				return ""; // kosongkan jika tidak ada payment_status
			}
		}

		return value;
	},
	onload: function (report) {
		$(document).on("click", ".submit-btn", function (e) {
			let docname = $(this).data("docname");

			alert(docname);
			// frappe.confirm(
			// 	`Yakin ingin submit ${docname}?`,
			// 	function () {

			// 		frappe.call({
			// 			method: "frappe.client.submit",
			// 			args: {
			// 				doctype: "Sales Order", // ganti sesuai doctype
			// 				name: docname
			// 			},
			// 			callback: function (r) {
			// 				frappe.msgprint("Berhasil di-submit");
			// 				report.refresh();
			// 			}
			// 		});

			// 	}
			// );
		});
	}
};
