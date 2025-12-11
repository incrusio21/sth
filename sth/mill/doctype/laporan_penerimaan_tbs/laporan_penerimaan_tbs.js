// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Laporan Penerimaan TBS", {
    refresh(frm) {
        frm.set_df_property("items", "cannot_add_rows", true)
    },

    get_data_timbangan(frm) {
        if (!frm.doc.docstatus != 1) {
            return
        }

        if (!frm.doc.tipe) {
            frappe.throw("Silahkan isi tipe TBS terlebih dahulu")
        }

        frm.call("get_timbangan")
            .then((res) => {
                frappe.model.sync(res);
                frm.refresh();
            })
    }
});
