// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Project", {
    refresh(frm) {
        if (frm.doc.status !== "Cancelled" && frm.doc.for_proposal) {
            frm.add_custom_button(
                __("Adendum"), () => {
                    frappe.model.open_mapped_doc({
                        method: "sth.legal.custom.project.make_project_adendum",
                        frm: cur_frm,
                        freeze_message: __("Adendum Revision ..."),
                    });
                },
                __("Create")
            );
        }
	}
});