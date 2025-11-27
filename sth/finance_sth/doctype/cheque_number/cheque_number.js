// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cheque Number", {
	refresh(frm) {
        frm.disable_save();
	},
});
