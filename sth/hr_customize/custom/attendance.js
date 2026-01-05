// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on('Attendance', {
    refresh(frm){
        sth.form.show_reset_payment_log(frm)
    }
})