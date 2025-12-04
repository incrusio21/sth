// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Security Check Point", {
    setup(frm) {
        frm.set_query("divisi", sth.queries.divisi)
    },

    transaction_type(frm) {
        frm.trigger('clear_fields')
    },

    clear_fields(frm) {
        const field_clear = ["receive_type", "dispatch_type"]
        field_clear.forEach((row) => {
            frm.set_value(row, "")
        })
    }
});
