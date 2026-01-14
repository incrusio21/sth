// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee Potongan", {
	refresh(frm) {
		frm.set_df_property("details", "cannot_add_rows", true);
		frm.set_query("unit", function () {
			return {
				filters: {
					company: ["=", frm.doc.company]
				}
			};
		});

		frm.set_query("bank_account", function () {
			return {
				filters: {
					company: ["=", frm.doc.company],
					unit: ["=", frm.doc.unit],
				}
			};
		});
	},
});
