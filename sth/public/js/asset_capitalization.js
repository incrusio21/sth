frappe.ui.form.on('Asset Capitalization', {
    refresh: function(frm) {
        if (frm.doc.docstatus == 0) {
            frm.add_custom_button(__('Get Items from Purchase Invoice'), function() {

                let d = new frappe.ui.Dialog({
                    title: __('Select Purchase Invoice'),
                    fields: [
                        {
                            label: __('Purchase Invoice'),
                            fieldname: 'purchase_invoice',
                            fieldtype: 'Link',
                            options: 'Purchase Invoice',
                            reqd: 1,
                            get_query: function() {
                                return {
                                    filters: {
                                        'docstatus': 1,
                                        'cwip_asset': 1,
                                        'company': frm.doc.company
                                    }
                                };
                            }
                        }
                    ],
                    primary_action_label: __('Get Items'),
                    primary_action(values) {
                        get_purchase_invoice_items(frm, values.purchase_invoice);
                        d.hide();
                    }
                });
                d.show();
            });
        }
    }
});

function get_purchase_invoice_items(frm, purchase_invoice) {
    if (!purchase_invoice) {
        frappe.msgprint(__('Please select a Purchase Invoice'));
        return;
    }

    frappe.call({
        method: 'frappe.client.get',
        args: {
            doctype: 'Purchase Invoice',
            name: purchase_invoice
        },
        callback: function(r) {
            if (r.message) {
                let pi = r.message;
                
                if (pi.unit) {
                    frm.set_value('unit', pi.unit);
                }
                
                frm.clear_table('service_items');
                
                if (pi.items && pi.items.length > 0) {
                    pi.items.forEach(function(item) {
                        let row = frm.add_child('service_items');
                        row.item_code = item.item_code;
                        row.qty = item.qty;
                        row.uom = item.uom;
                        row.rate = item.rate;
                        row.expense_account = item.expense_account;
                        row.amount = item.amount;
                        row.cost_center = item.cost_center;
                    });
                    
                    frm.refresh_field('service_items');
                    frappe.msgprint(__('Items added from Purchase Invoice: {0}', [purchase_invoice]));
                } else {
                    frappe.msgprint(__('No items found in Purchase Invoice'));
                }
            }
        }
    });
}