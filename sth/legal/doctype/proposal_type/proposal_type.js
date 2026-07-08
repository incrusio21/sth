// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Proposal Type", {
    refresh(frm){
        frm.trigger("setup_column")
        set_akun_query(frm)
    },
    document_type(frm){
        frm.clear_table("fields")
        frm.trigger("setup_column")
    },
    setup_column(frm){
        frappe.require("configure-column.bundle.js", function () {
            new sth.ConfigureColumn.Controller(frm.fields_dict.fields_html.wrapper, {
                doctype: "Proposal",
                fields: "fields",
                frm: frm,
            });
        });
    }
});


function set_akun_query(frm, cdt, cdn) {

    frm.set_query("account", "hutang_usaha_proposal_type", function (doc, cdt, cdn) {
        let row = locals[cdt][cdn];

        return {
            filters: {
                company: row.company,
                is_group: 0 
            }
        };
    });
     frm.set_query("account", "hutang_invoice_proposal_type", function (doc, cdt, cdn) {
        let row = locals[cdt][cdn];

        return {
            filters: {
                company: row.company,
                is_group: 0 
            }
        };
    });
      frm.set_query("account", "uang_muka_proposal_type", function (doc, cdt, cdn) {
        let row = locals[cdt][cdn];

        return {
            filters: {
                company: row.company,
                is_group: 0 
            }
        };
    });
}