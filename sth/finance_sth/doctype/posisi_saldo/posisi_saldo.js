// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Posisi Saldo", {
	refresh(frm) {
        filterFields(frm)
	},
});


function filterFields(frm) {
    frm.set_query('unit', (doc)=>{
        return{
            filters:{
                company: ["=", doc.company]
            }
        }
    })
    frm.set_query('bank_account', (doc)=>{
        return{
            filters:{
                company: ["=", doc.company],
                unit: ["=", doc.unit],
            }
        }
    })
}