frappe.ui.form.on('Salary Slip', {
    refresh: function(frm) {
        if (frm.doc.docstatus == 1) {
            frm.add_custom_button(__('Payment Voucher'), function() {
                frappe.model.open_mapped_doc({
                    method: "sth.overrides.salary_slip.make_payment_entry",
                    frm: frm
                });
            }, __('Create'));
        }
    }
});