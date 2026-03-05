// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Payment Notification Settings", {
// 	refresh(frm) {

// 	},
// });


frappe.ui.form.on("Payment Notification Settings", {
    setup(frm) {
        frm.set_query("document_name", function() {
            return {
                query: "sth.legal.doctype.payment_notification_settings.payment_notification_settings.get_outstanding_doctypes"
            };
        });
    }
});