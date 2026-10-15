// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Mill Settings", {
	setup(frm) {
		frm.set_query("account", "akun_difference", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			return {
				filters: {
					company: row.company,
					is_group: 0,
				},
			};
		});
	},
});
