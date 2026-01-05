// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on('Attendance', {
    refresh: function(frm) {
		sth.form.show_reset_payment_log(frm)
        check_and_set_leave_type(frm);
    },
    
    employee: function(frm) {
        check_and_set_leave_type(frm);
    },
    
    status: function(frm) {
        check_and_set_leave_type(frm);
    }
});

function check_and_set_leave_type(frm) {
	console.log("LAKUKAN")
    if (frm.doc.employee && frm.doc.status == "On Leave") {
		console.log("CHECK")
        frappe.db.get_value('Employee', frm.doc.employee, 'designation', function(r) {
			console.log(r.designation)
            if (r && r.designation === "NS30") {
                frm.set_value('leave_type', 'OFF Hari Ke 7');
                
                frm.set_df_property('leave_type', 'read_only', 1);
            } else {
                frm.set_df_property('leave_type', 'read_only', 0);
            }
        });
    } else {
        frm.set_df_property('leave_type', 'read_only', 0);
    }
}