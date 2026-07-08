// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Blok", {
	refresh(frm) {
		frm.set_query("status", function() {
			return {
				filters: {
					is_perawatan: 1
				}
			};
		});
	},
});