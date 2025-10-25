// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pengajuan Panen Kontanan", {
	refresh(frm) {
        frm.set_df_property("hasil_panen", "cannot_add_rows", true);

        frm.set_query("bkm_panen", function(doc){
            if(!doc.company){
                frappe.throw("Please Select Company First")
            }

            return{
                filters: {
                    company: doc.company,
                    is_kontanan: 1,
                    is_rekap: 1
                }
            }
        })
	},
    upah_panen_total(frm){
        frm.doc.grand_total = frm.doc.upah_panen_total
    }
});
