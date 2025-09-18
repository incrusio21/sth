// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pengajuan Panen Kontanan", {
	refresh(frm) {
        frm.set_query("bkm_panen", function(doc){
            if(!doc.company){
                frappe.throw("Please Select Company First")
            }

            return{
                filters: {
                    company: doc.company,
                    is_kontananan: 1,
                    is_used: 0,
                }
            }
        })
	},
    upah_panen_total(frm){
        frm.doc.grand_total = frm.doc.upah_panen_total
    }
});
