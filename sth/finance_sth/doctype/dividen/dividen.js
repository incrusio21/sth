// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Dividen", {
	refresh(frm) {
        setFilterOne(frm)
	},
    company(frm){
        setFilterOne(frm)
    },
    unit_one(frm){
        setFilterOne(frm)
    }
});

function setFilterOne(frm) {
    frm.set_query("unit_one", (doc)=>{
        return {
            filters:{
                company: doc.company_one
            }
        }
    })
    frm.set_query("bank_account_one", (doc)=>{
        return {
            filters:{
                company: doc.company_one,
                unit: doc.unit_one,
                bank: doc.bank_one
            }
        }
    })
}
