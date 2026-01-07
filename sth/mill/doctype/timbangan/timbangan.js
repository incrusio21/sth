// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt
frappe.provide("sth.utils")

frappe.ui.form.on("Timbangan", {
    refresh(frm) {
        frm.ignore_doctypes_on_cancel_all = ["TBS Ledger Entry"]
    },

    readWeight(frm) {
        frappe.scaleConnection = frappe.scaleConnection || new sth.utils.scale_connection();
        frappe.scaleConnection.connect().then(() => {
            frappe.scaleConnection.startReading((weight) => {
                if (weight.includes('kg')) {
                    let weight_number = parseFloat(weight.split('kg')[0])
                    frm.doc.live_weight = weight_number
                    frm.refresh_field("live_weight")
                }
            });
        })
    },

    set_netto(row) {
        const bruto = row.bruto || 0
        const tara = row.tara || 0
        frappe.model.set_value(row.doctype, row.name, "netto", bruto - tara)
    },


});

frappe.ui.form.on("Timbangan Item", {
    bruto(frm, dt, dn) {
        var row = locals[dt][dn]
        frm.events.set_netto(row)
    },

    tara(frm, dt, dn) {
        var row = locals[dt][dn]
        frm.events.set_netto(row)
    },
});


window.addEventListener("beforeunload", () => {
    if (frappe.scaleConnection) {
        frappe.scaleConnection.close();
    }
});
