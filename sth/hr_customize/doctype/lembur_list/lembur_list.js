// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Lembur List", {
	refresh(frm) {
        frm.set_query("employee", function (doc) {
            return {
                query: "sth.hr_customize.doctype.lembur_list.lembur_list.employee_selected_staff_query",
                filters: {
                    company: doc.company,
                }
            }
        })
	},
});
