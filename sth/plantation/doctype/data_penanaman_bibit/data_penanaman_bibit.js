// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Data Penanaman Bibit", {
	onload: function(frm) {      
        if (frm.is_new() && !frm.doc.posting_time) {
            let now = frappe.datetime.now_time(); 
            frm.set_value("posting_time", now);
        }
    },
    refresh(frm) {
        frm.set_query("data_penyemaian_bibit", function(doc) {
            return {
                "filters": [
                    ["company",  "=", doc.company],
                    ["docstatus",  "=", 1],                    
                ]
            };            
        });
	}
});
