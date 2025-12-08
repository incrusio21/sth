// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.provide("sth.queries")
frappe.ui.form.on("Berita Acara", {
    onload(frm) {
        frm.set_query("item_code", "table_klkc", sth.queries.item_by_subtype)
    },

    refresh(frm) {
        if (frm.is_new()) {
            frm.trigger('set_default_reqdate')
        }

        if (frm.doc.docstatus == 1) {
            frm.add_custom_button("Material Request", function () {
                frappe.model.open_mapped_doc({
                    method: "sth.buying_sth.doctype.berita_acara.berita_acara.create_mr",
                    frm,
                    run_link_triggers: 1
                })
            }, __("Create"))
        }
    },

    set_default_reqdate(frm) {
        const required_date = frappe.datetime.add_days(frm.doc.date, 7)
        frm.set_value("required_date", required_date)
    },
});
