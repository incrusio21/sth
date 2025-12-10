// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Laporan Penerimaan TBS", {
    refresh(frm) {
        frm.set_df_property("items", "cannot_add_rows", true)
    },
});
