// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Payment Entry", {
    refresh(frm) {
        frm.set_query("reference_doctype", "references", function () {
            return {
                query: "sth.hr_customize.custom.payment_entry.get_payment_reference",
                filters: { 
                    party_type: frm.doc.party_type 
                },
            };
        });
        
        frm.set_query('custom_cheque_number', () => {
            return {
                filters: {
                    reference_doc: null, 
                    reference_name: null, 
                    bank_account: frm.doc.bank_account 
                }
            }
        })
        
        frm.set_query('unit', (doc) => {
            return {
                filters: {
                    company: ["=", doc.company],
                }
            }
        })

        frm.set_query('reference_name', "references", (doc) => {
            return {
                filters: {
                    docstatus: 1,
                    company: ["=", doc.company],
                    unit: doc.unit   
                }
            }
        })

        frm.set_query('bank_account', (doc) => {
            return {
                filters: {
                    unit: ["=", doc.unit],
                    company: ["=", doc.company],
                }
            }
        })
    },
    party_type(frm){
        frm.set_value("internal_employee", 0)
    },
    unit(frm){
        if(!frm.doc.unit) return
        
        frm.clear_table("references")
        frm.refresh_field("references")
    },
    internal_employee(frm){
        if(!frm.doc.internal_employee) return

        frappe.call({
            method: "sth.hr_customize.custom.payment_entry.get_internal_employee",
            callback(data){
                frm.set_value("party", data.message)
            }
        })
    }
});
