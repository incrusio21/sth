// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Tax Rate", {
	refresh(frm) {

	},
	onload: function (frm) {
		frm.set_query("account", "tax_rate_account", function (doc, cdt, cdn) {
			let row = locals[cdt][cdn];
			return {
				"filters": {
					"company": row.company,
					"account_type": "Tax"
				},
			};
		});
	},
});


frappe.ui.form.on("Tax Rate Account", {
	company: function(frm){
		frm.set_query("account", "tax_rate_account", function (doc, cdt, cdn) {
			let row = locals[cdt][cdn];
			return {
				"filters": {
					"company": row.company,
					"account_type": "Tax"
				},
			};
		});
	}
});

