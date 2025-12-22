// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Tutup Buku Fisik", {
    setup(frm) {
        frm.set_query("warehouse", (doc) => {
            return {
                filters: {
                    company: doc.company,
                    is_group: 0
                }
            }
        })
    },

    periode(frm) {
        frm.trigger('set_start_end_dates')
    },

    set_start_end_dates(frm) {
        if (frm.doc.periode) {
            frappe.call({
                method: "hrms.payroll.doctype.payroll_entry.payroll_entry.get_start_end_dates",
                args: {
                    payroll_frequency: frm.doc.periode,
                    start_date: frm.doc.tanggal_dibuat,
                },
                callback: function (r) {
                    if (r.message) {
                        frm.set_value("from_date", r.message.start_date);
                        frm.set_value("to_date", r.message.end_date);
                    }
                },
            });
        }
    },

    refresh(frm) {

    },
});
