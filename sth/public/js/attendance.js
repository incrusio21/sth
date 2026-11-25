// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on('Attendance', {
    refresh: function(frm) {
		sth.form.show_reset_payment_log(frm)
        // check_and_set_leave_type(frm);
        frm.set_df_property('status', 'options', [
            'Present',
            'On Leave',
            'Absent',
            'Work From Home',
            '7th Day Off'
        ].join('\n'));

        pasang_formatter_link_attendance();

    },
    
    employee: function(frm) {
        // check_and_set_leave_type(frm);
    },
    
    status: function(frm) {
        // check_and_set_leave_type(frm);
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

// Link di form Attendance ditampilkan apa adanya (ID), bukan judulnya.
// frappe.form.formatters.Link itu global untuk seluruh desk; dulu pembungkus ini
// cuma memeriksa `if (doc)` sehingga begitu Attendance dibuka, Link Title di form,
// grid dan Report Builder doctype lain ikut hilang sampai halaman dimuat ulang.
// Sekarang hanya untuk dokumen Attendance, dan cuma dipasang sekali per sesi.
let formatter_link_attendance_terpasang = false;

function pasang_formatter_link_attendance() {
    if (formatter_link_attendance_terpasang) return;
    formatter_link_attendance_terpasang = true;

    const original_link_formatter = frappe.form.formatters.Link;
    frappe.form.formatters.Link = function (value, docfield, options, doc) {
        if (doc && (doc.doctype === "Attendance" || doc.parenttype === "Attendance")) {
            return value || "";
        }
        // Doctype lain tetap pakai formatter asli
        return original_link_formatter(value, docfield, options, doc);
    };
}
