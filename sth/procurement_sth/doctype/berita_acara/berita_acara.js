// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.provide("sth.queries")
frappe.ui.form.on("Berita Acara", {
    onload(frm) {
        frm.set_query("item_code", "table_klkc", sth.queries.item_by_subtype)
    },

    refresh(frm) {
        if (frm.doc.docstatus == 1) {
            frm.add_custom_button("Material Request", function () {
                frappe.model.open_mapped_doc({
                    method: frappe.model.get_server_module_name(frm.doctype) + ".create_mr",
                    frm,
                    run_link_triggers: 1
                })
            }, __("Create"))
        }

        if (frm.is_new()) {
            frm.set_value("make", frappe.session.user)
        }
    },

});

frappe.ui.form.on("Berita Acara Detail", {
    form_render(frm, dt, dn) {
        console.log("Form Terbuka");
        frm.get_field('table_klkc').$wrapper.find(".grid-duplicate-row").off("click")
    }
})
