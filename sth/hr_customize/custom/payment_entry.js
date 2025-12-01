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
                    bank_account: (frm.doc.paid_from ? frm.doc.paid_from: null)
                }
            }
        })
    },
    party_type(frm){
        frm.set_value("internal_employee", 0)
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
