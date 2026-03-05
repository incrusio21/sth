// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

// frappe.ui.form.on("PDO Account Settings", {
// 	refresh(frm) {

// 	},
// });

frappe.ui.form.on("PDO Account Settings", {
    setup(frm) {
        frm.fields_dict["pdo_account_settings_table"].grid.get_field("kas_ho_account").get_query = function(doc, cdt, cdn) {
            let row = locals[cdt][cdn];
            return {
                filters: {
                    company: row.company,
                    is_group: 0
                }
            };
        };

        frm.fields_dict["pdo_account_settings_table"].grid.get_field("kas_dan_bank_dalam_perjalanan").get_query = function(doc, cdt, cdn) {
            let row = locals[cdt][cdn];
            return {
                filters: {
                    company: row.company,
                    is_group: 0
                }
            };
        };
    }
});