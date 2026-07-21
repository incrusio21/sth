// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("PDO Type", {
	refresh(frm) {
		set_akun_query(frm);
	},
});

function set_akun_query(frm, cdt, cdn) {
	frm.fields_dict['pdo_type_account'].grid.get_field('account').get_query = function (doc, cdt, cdn) {
		let row = locals[cdt][cdn];
		return {
			filters: {
				company: row.company,
				is_group: 0
			}
		};
	};
}