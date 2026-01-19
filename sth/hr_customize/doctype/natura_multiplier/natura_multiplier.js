// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Natura Multiplier", {
	refresh(frm) {

	},
    employee_multiplier(frm){
        frm.trigger("calculate_multiplier")
    },
    partner_multiplier(frm){
        frm.trigger("calculate_multiplier")
    },
    child_multiplier(frm){
        frm.trigger("calculate_multiplier")
    },
    pkp(frm){
        frm.trigger("calculate_multiplier")
    },
    calculate_multiplier(frm){
        if(in_list(frm.doc.pkp, "T")){
            frm.doc.partner_multiplier = 0
        }

        if(in_list(frm.doc.pkp, "0")){
            frm.doc.child_multiplier = 0
        }

        frm.set_value("multiplier", 
            (frm.doc.employee_multiplier || 0) + 
            (frm.doc.partner_multiplier || 0) +
            (frm.doc.child_multiplier || 0)
        )
    }
});
