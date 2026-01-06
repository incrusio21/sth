frappe.ui.form.on('Daftar BPJS', {
    refresh: function(frm) {
    	console.log(frm.doc.daftar_bpjs_employee)
        if (frm.doc.docstatus == 0 && frm.doc.daftar_bpjs_employee.length == 0)  {
            frm.add_custom_button(__('Get Employee'), function() {
                frm.disable_save();
                frappe.show_alert({
                    message: __('Loading employees, please wait...'),
                    indicator: 'blue'
                }, 5);
                
                frappe.call({
                    doc: frm.doc,
                    method: 'get_employee',
                    freeze: true,
                    freeze_message: __('Fetching employee data...'),
                    callback: function(r) {
                        frm.enable_save();
                        frm.refresh_fields();
                        frm.dirty()
                        
                        if (r.message) {
                            frappe.show_alert({
                                message: __('Successfully loaded {0} employee(s)', [r.message]),
                                indicator: 'green'
                            }, 5);
                        }
                    },
                    error: function() {
                        frm.enable_save();
                        frappe.show_alert({
                            message: __('Error loading employees'),
                            indicator: 'red'
                        }, 5);
                    }
                });
            });
        }
    }
});