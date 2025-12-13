// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Rekap Timbangan Panen", {
	refresh(frm) {

	},
    get_items(frm) {
        frm.cscript.get_bkm_panen_data(frm)
    }
});

sth.plantation.RekapTimbanganPanen = class RekapTimbanganPanen extends frappe.ui.form.Controller {
    refresh() {
        let me = this
        this.frm.set_df_property("details", "cannot_add_rows", true);
        this.frm.set_df_property("details", "cannot_delete_rows", true);

        for (const fieldname of ["transaction_date", "company", "unit", "divisi"]) {
            frappe.ui.form.on(this.frm.doctype, fieldname, function(frm) {
                me.frm.clear_table("details")
                me.frm.refresh_fields()
            });
        }
    }

    get_bkm_panen_data(){
        let me = this
        let doc = this.frm.doc

        if(!(doc.transaction_date && doc.unit && doc.divisi)) return
        
        frappe.call({
            method: "sth.plantation.doctype.rekap_timbangan_panen.rekap_timbangan_panen.get_bkm_panen",
            args: {
                posting_date: doc.transaction_date,
                unit: doc.unit,
                divisi: doc.divisi,
            },
            freeze: true,
            callback: function (data) {
                me.frm.set_value(data.message)
            }
        })
    }
}

cur_frm.script_manager.make(sth.plantation.RekapTimbanganPanen);
