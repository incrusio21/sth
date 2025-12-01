// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cheque Book", {
    cheque_start_no(frm){
        numberInput(frm,"cheque_start_no");
    },

    cheque_end_no(frm){
        numberInput(frm,"cheque_end_no");
    },

    cheque_warning_no(frm){
        numberInput(frm,"cheque_warning_no");
    },
});


function numberInput(frm, fieldname) {
    let val = frm.doc[fieldname];

    if (val && /[^0-9]/.test(val)) {
        frm.set_value(fieldname, val.replace(/[^0-9]/g, ""));
        frm.refresh_field(fieldname)
    }
}
