// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Data Pencatatan Dobletone Dan Afkir", {
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
	},
    qty(frm){
        if(frm.doc.qty>frm.doc.available_qty){
            frm.set_value("qty", frm.doc.available_qty);
            frappe.msgprint("Jumlah Bibit must not be greater than " + frm.doc.available_qty);
        }else if(frm.doc.qty<0){
            frm.set_value("qty", frm.doc.available_qty);
            frappe.msgprint("Jumlah Bibit must not be less than 0");
        }
    }
});