// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Analisa Press Cake", {
    refresh(frm) {
        if (frm.doc.docstatus != 2) {
            frm.trigger("show_warning_list")
        }
    },

    show_warning_list(frm) {
        console.log(frm.doc.warning_list);

        let warning_lists = JSON.parse(frm.doc.warning_list || "[]");
        if (!warning_lists.length) {
            frm.set_df_property("section_break_seyf", "hidden", 1)
            return
        }

        const message = `
			<div class="warning-message form-message yellow">
				<ul class="mb-0">
					${warning_lists.map(item => `<li>${item}</li>`).join('')}
				</ul>
			</div>
		`

        frm.get_field("warning_message").$wrapper.html(message)
        frm.set_df_property("section_break_seyf", "hidden", 0)
    },
});
