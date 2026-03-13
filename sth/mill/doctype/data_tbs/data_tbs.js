// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Data TBS", {
    refresh(frm) {

    },

    get_data(frm) {
        frm.call("get_data").then(() => {
            frm.refresh()
        })
    }
});
