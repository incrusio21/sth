// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Purchase Type", {
    refresh(frm){
        frm.trigger("setup_column")
    },
    document_type(frm){
        frm.clear_table("fields")
        frm.trigger("setup_column")
    },
    setup_column(frm){
        frappe.require("configure-column.bundle.js", function () {
            new sth.ConfigureColumn.Controller(frm.fields_dict.fields_html.wrapper, {
                doctype: frm.doc.document_type,
                fields: "fields",
                frm: frm,
            });
        });
    }
});