// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Security Check Point", {
    setup(frm) {
        frm.set_query("divisi", sth.queries.divisi)
        frm.set_query("unit", (doc) => {
            return {
                filters: {
                    company: doc.company
                }
            }
        })

        frm.set_query("ticket_number", (doc) => {
            return {
                filters: {
                    exit: false
                }
            }
        })
    },

    onload(frm) {
        cur_frm.add_fetch("do_no", "unit", "unit")
        cur_frm.add_fetch("spb", "unit", "unit")
    },

    transaction_type(frm) {
        frm.events.clear_fields(frm, "transaction")
    },

    receive_type(frm) {
        frm.events.clear_fields(frm, "receive")
    },

    dispatch_type(frm) {
        frm.events.clear_fields(frm, "dispatch")
    },

    return_type(frm) {
        frm.events.clear_fields(frm, "dispatch")
    },


    clear_fields(frm, type) {
        const field_clear = {
            transaction: ["receive_type", "dispatch_type", "return_type"],
            receive: ["spb", "purchase_order"],
            dispatch: ["do_no", "items_do"]
        }
        field_clear[type].forEach((row) => {
            frm.set_value(row, "")
        })
    },

    exit(frm) {
        const time = frm.doc.exit ? moment().format("HH:mm:ss") : "00:00:00"
        frm.set_value("vehicle_exit_time", time)
    }
});
