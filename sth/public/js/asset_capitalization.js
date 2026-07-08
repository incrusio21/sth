frappe.ui.form.on('Asset Capitalization', {
    refresh: function(frm) {
        if (frm.doc.docstatus == 0) {

            // --- Get from Project ---
            frm.add_custom_button(__('Get from Project'), function() {
                let d = new frappe.ui.Dialog({
                    title: __('Select Project'),
                    fields: [
                        {
                            label: __('Project'),
                            fieldname: 'project',
                            fieldtype: 'Link',
                            options: 'Project',
                            reqd: 1
                        }
                    ],
                    primary_action_label: __('Get BAPP'),
                    primary_action(values) {
                        get_bapp_items(frm, 'project', values.project);
                        d.hide();
                    }
                });
                d.show();
            }, __('Get Items'));

            // --- Get from Proposal ---
            frm.add_custom_button(__('Get from Proposal'), function() {
                let d = new frappe.ui.Dialog({
                    title: __('Select Proposal'),
                    fields: [
                        {
                            label: __('Proposal'),
                            fieldname: 'proposal',
                            fieldtype: 'Link',
                            options: 'Proposal',
                            reqd: 1,
                            get_query: function() {
                                return { filters: { docstatus: 1 } };
                            }
                        }
                    ],
                    primary_action_label: __('Get BAPP'),
                    primary_action(values) {
                        get_bapp_items(frm, 'proposal', values.proposal);
                        d.hide();
                    }
                });
                d.show();
            }, __('Get Items'));

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
            }, __('Get Items'));
        }
    }
});

function get_bapp_items(frm, source_type, source_value) {
    if (!source_value) {
        frappe.msgprint(__('Please select a value'));
        return;
    }

    let method_map = {
        project: 'sth.overrides.asset_capitalization.get_bapp_from_project',
        proposal: 'sth.overrides.asset_capitalization.get_bapp_from_proposal'
    };

    let args_map = {
        project: { project: source_value },
        proposal: { proposal: source_value }
    };

    frappe.call({
        method: method_map[source_type],
        args: args_map[source_type],
        callback: function(r) {
            let bapps = r.message || [];
            if (!bapps.length) {
                frappe.msgprint(__('Tidak ada BAPP ditemukan'));
                return;
            }

            // Hindari duplikat: kumpulkan yang sudah ada
            let existing = new Set(
                (frm.doc.asset_capitalization_bapp_item || []).map(row => row.bapp)
            );

            let added = 0;
            bapps.forEach(function(b) {
                if (existing.has(b.name)) return;
                let row = frm.add_child('asset_capitalization_bapp_item');
                row.bapp         = b.name;
                row.supplier     = b.supplier;
                row.supplier_name = b.supplier_name;
                row.proposal     = b.proposal;
                row.project      = b.project;
                row.grand_total  = b.grand_total;
                row.status       = b.status;
                existing.add(b.name);
                added++;
            });

            frm.refresh_field('asset_capitalization_bapp_item');
            frappe.msgprint(__('Berhasil menambahkan {0} BAPP', [added]));
        }
    });
}

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