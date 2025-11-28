// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Purchase Order Type", {
    onload(frm){
        frappe.require("configure-column.bundle.js", function () {
            new sth.ConfigureColumn.Controller(frm.fields_dict.fields_html.wrapper, {
                doctype: "Purchase Order Item",
                fields: "fields",
                frm: frm,
            });
        });
    }
});