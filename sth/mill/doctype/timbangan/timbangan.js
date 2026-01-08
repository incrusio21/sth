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

    spb(frm) {
        frm.clear_table('spb_detail')
        if (!frm.doc.spb) {
            return
        }
        const base = frappe.model.get_server_module_name(frm.doctype)
        frappe.xcall(`${base}.get_spb_detail`, { spb: frm.doc.spb })
            .then((res) => {
                res.forEach(row => {
                    frm.add_child('spb_detail', row)
                });
                frm.refresh_field('spb_detail')
            })
    },
});



window.addEventListener("beforeunload", () => {
    if (frappe.scaleConnection) {
        frappe.scaleConnection.close();
    }
});
