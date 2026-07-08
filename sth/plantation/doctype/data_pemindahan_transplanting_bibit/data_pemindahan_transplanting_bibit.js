// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Data Pemindahan Transplanting Bibit", {
    setup(frm) {

        frm.set_query("batch", function() {
            return {
                query: "sth.api.get_batch_penyemaian"
            };
        });

    },
	onload: function(frm) {      
        if (frm.is_new() && !frm.doc.posting_time) {
            let now = frappe.datetime.now_time(); 
            frm.set_value("posting_time", now);
        }
    },
    refresh(frm) {
        frm.set_query("data_penyemaian_bibit", function(doc) {
            return {
                "filters": [
                    ["company",  "=", doc.company],
                    ["docstatus",  "=", 1],                    
                ]
            };            
        });
	},
    data_penyemaian_bibit(frm) {

        if (!frm.doc.data_penyemaian_bibit) {
            frm.set_value("available_qty", 0);
            return;
        }

        frappe.call({
            method: "sth.plantation.doctype.data_pemindahan_transplanting_bibit.data_pemindahan_transplanting_bibit.get_available_qty",
            args: {
                data_penyemaian_bibit: frm.doc.data_penyemaian_bibit
            },
            callback(r) {

                if (r.message) {
                    frm.set_value(
                        "available_qty",
                        r.message
                    );
                }

            }
        });

    },
    batch(frm) {

        if (!frm.doc.batch) {
            frm.set_value("data_penyemaian_bibit", "");
            return;
        }

        frappe.db.get_value(
            "Data Penyemaian Bibit",
            {
                batch: frm.doc.batch,
                docstatus: 1
            },
            "name"
        ).then(r => {

            if (r.message && r.message.name) {

                frm.set_value(
                    "data_penyemaian_bibit",
                    r.message.name
                );

            } else {

                frm.set_value(
                    "data_penyemaian_bibit",
                    ""
                );

                frappe.msgprint(
                    "Data Penyemaian Bibit untuk batch ini tidak ditemukan."
                );
            }

        });

    }
});
