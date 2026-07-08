// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("STH Accounting Settings", {
	refresh(frm) {
		set_account_filters(frm)
	},
});

function set_account_filters(frm){
	frm.set_query("account", "sth_accounting_settings_payroll", function (doc, cdt, cdn) {
		let row = locals[cdt][cdn];

		return {
			filters: {
				company: row.company,
				is_group: 0 
			}
		};
	});
	frm.set_query("account", "sth_accounting_settings_alokasi_gaji_bengkel", function (doc, cdt, cdn) {
		let row = locals[cdt][cdn];

		return {
			filters: {
				company: row.company,
				is_group: 0 
			}
		};
	});
	frm.set_query("account", "sth_accounting_settings_reparasi_bengkel_account", function (doc, cdt, cdn) {
		let row = locals[cdt][cdn];

		return {
			filters: {
				company: row.company,
				is_group: 0 
			}
		};
	});
	frm.set_query("account", "sth_accounting_settings_biaya_bengkel_dialokasi", function (doc, cdt, cdn) {
		let row = locals[cdt][cdn];

		return {
			filters: {
				company: row.company,
				is_group: 0 
			}
		};
	});
}


