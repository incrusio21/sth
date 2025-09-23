// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Rekap Timbangan Panen", {
// 	refresh(frm) {

// 	},
// });

sth.plantation.RekapTimbanganPanen = class RekapTimbanganPanen extends frappe.ui.form.Controller {
    refresh() {
        let me = this
        this.frm.set_df_property("details", "cannot_add_rows", true);
        this.frm.set_df_property("details", "cannot_delete_rows", true);

        for (const fieldname of ["blok", "panen_date"]) {
            frappe.ui.form.on(this.frm.doctype, fieldname, function() {
                me.get_bkm_panen_data()
            });
        }
    }

    get_bkm_panen_data(item){
        let me = this
        let doc = this.frm.doc

        if(!(doc.blok && doc.panen_date)) return
        
        frappe.call({
            method: "sth.plantation.doctype.rekap_timbangan_panen.rekap_timbangan_panen.get_bkm_panen",
            args: {
                blok: doc.blok,
                posting_date: doc.panen_date
            },
            freeze: true,
            callback: function (data) {
                me.frm.set_value(data.message)
            }
        })
    }
}

cur_frm.script_manager.make(sth.plantation.RekapTimbanganPanen);
