// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Unit", {
	refresh(frm) {
		frm.set_query(`bank_account`, () => {
            return {
                filters: {
                    "account_type": "Bank",
                    "company": frm.doc.company
                }
            }
        })
	},
});
