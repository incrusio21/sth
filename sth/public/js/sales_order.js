frappe.ui.form.on('Sales Order', {
	customer: function(frm) {
		set_komoditi_filter(frm);

        if (frm.doc.komoditi) {
            frm.set_value('komoditi', '');
            frm.clear_table('keterangan_per_komoditi');
            frm.refresh_field('keterangan_per_komoditi');
        }
    },
    
    refresh: function(frm) {
        set_komoditi_filter(frm);
        set_query_unit(frm)
    },

    komoditi: function(frm) {
		if (frm.doc.komoditi && frm.doc.customer) {
            validate_komoditi(frm);
        }

        if (frm.doc.komoditi) {
            frm.clear_table('keterangan_per_komoditi');
            
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Komoditi',
                    name: frm.doc.komoditi
                },
                callback: function(r) {
                    if (r.message && r.message.keterangan_per_komoditi) {
                        r.message.keterangan_per_komoditi.forEach(function(row) {
                            let child_row = frm.add_child('keterangan_per_komoditi');
                            child_row.keterangan = row.keterangan;
                            child_row.parameter = row.parameter;
                        });
                        
                        frm.refresh_field('keterangan_per_komoditi');
                    }
                }
            });
        }
    },
    onload: function(frm){
        set_query_unit(frm)
    },
    company: function(frm){
        set_query_unit(frm)
    }
});

function set_komoditi_filter(frm) {
    if (frm.doc.customer) {
        frappe.call({
            method: 'frappe.client.get',
            args: {
                doctype: 'Customer',
                name: frm.doc.customer
            },
            callback: function(r) {
                if (r.message && r.message.custom_customer_komoditi) {
                    let komoditi_list = r.message.custom_customer_komoditi.map(function(row) {
                        return row.komoditi;
                    });
                
                    if (komoditi_list.length > 0) {
                        frm.set_query('komoditi', function() {
                            return {
                                filters: {
                                    'name': ['in', komoditi_list]
                                }
                            };
                        });
                    } else {
                        frm.set_query('komoditi', function() {
                            return {
                                filters: {
                                    'name': ['in', []]
                                }
                            };
                        });
                    }
                }
            }
        });
    } else {
        frm.set_query('komoditi', function() {
            return {};
        });
    }
}

function validate_komoditi(frm) {

    if (!frm.doc.customer) {
        return;
    }
    
    frappe.call({
        method: 'frappe.client.get',
        args: {
            doctype: 'Customer',
            name: frm.doc.customer
        },
        callback: function(r) {
            if (r.message && r.message.custom_customer_komoditi) {
                let komoditi_list = r.message.custom_customer_komoditi.map(function(row) {
                    return row.komoditi;
                });
                
                if (!komoditi_list.includes(frm.doc.komoditi)) {
                    frappe.msgprint({
                        title: __('Invalid Komoditi'),
                        indicator: 'red',
                        message: __('The selected Komoditi "{0}" is not linked to Customer "{1}". Please select a valid Komoditi.', [frm.doc.komoditi, frm.doc.customer])
                    });
                    frm.set_value('komoditi', '');
                }
            }
        }
    });
}
function set_query_unit(frm){
    frm.set_query('unit', function() {
        return {
            filters: {
                'company': frm.doc.company
            }
        };
    });
}