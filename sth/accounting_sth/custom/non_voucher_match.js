frappe.ui.form.on('Purchase Invoice', {
    voucher_type: function(frm) {
        toggle_non_voucher_section(frm);
        if (frm.doc.voucher_type === 'Non Voucher Match') {
            set_coa_filter(frm);
        }
    },
    
    refresh: function(frm) {
        toggle_non_voucher_section(frm);
        
        if (frm.doc.voucher_type === 'Non Voucher Match') {
            set_coa_filter(frm);
        }
    },
    
    validate: function(frm) {
        if (frm.doc.voucher_type === 'Non Voucher Match') {
            process_non_voucher_entries(frm);
        }
    },
    
    onload: function(frm) {
        // Add custom field for Non Voucher table if not exists
        if (!frm.fields_dict.non_voucher_match) {
            // This assumes you've created a child table field named 'non_voucher_match'
        }
    }
});

function toggle_non_voucher_section(frm) {
    if (frm.doc.voucher_type === 'Non Voucher Match') {
        frm.set_df_property('non_voucher_match', 'hidden', 0);
        frm.set_df_property('items', 'hidden', 1); // Hide regular items table
    } else {
        frm.set_df_property('non_voucher_match', 'hidden', 1);
        frm.set_df_property('items', 'hidden', 0);
    }
    frm.refresh_fields();
}

function set_coa_filter(frm) {
    // Set query filter for COA field in non_voucher_match table
    frm.set_query('coa', 'non_voucher_match', function(doc) {
        return {
            filters: {
                'company': doc.company,
                'is_group': 0
            }
        };
    });
}

function process_non_voucher_entries(frm) {
    if (!frm.doc.non_voucher_match || frm.doc.non_voucher_match.length === 0) {
        return; // No non-voucher entries to process
    }
    
    if (!frm.doc.company) {
        frappe.throw(__('Please select a Company first'));
        return;
    }
    
    // Get company accounts synchronously
    frappe.call({
        method: 'frappe.client.get',
        args: {
            doctype: 'Company',
            name: frm.doc.company
        },
        async: false,
        callback: function(r) {
            if (r.message) {
                let company = r.message;
                
                // Validate required accounts
                if (!company.account_default_item) {
                    frappe.throw(__('Account Default Item is not set in Company'));
                    return;
                }
                if (!company.ppn_account) {
                    frappe.throw(__('PPN Account is not set in Company'));
                    return;
                }
                if (!company.pph_account) {
                    frappe.throw(__('PPh Account is not set in Company'));
                    return;
                }
                
                // Clear existing items
                frm.clear_table('items');
                
                // Clear existing taxes
                frm.clear_table('taxes');
                
                let total_dpp = 0;
                let total_ppn = 0;
                let total_pph = 0;
                
                // Create hidden item entries with "Biaya" as item
                frm.doc.non_voucher_match.forEach((nv_row, idx) => {
                    let item_row = frm.add_child('items');
                    item_row.item_code = company.account_default_item; // Mandatory item
                    item_row.item_name = company.account_default_item; 
                    item_row.description = nv_row.description || 'Non Voucher Entry';
                    item_row.qty = 1;
                    item_row.rate = nv_row.dpp || 0;
                    item_row.amount = nv_row.dpp || 0;
                    item_row.uom = "Nos"
                    item_row.expense_account = nv_row.coa // Use COA or default
                    
                    total_dpp += (nv_row.dpp || 0);
                    total_ppn += (nv_row.ppn || 0);
                    total_pph += (nv_row.pph || 0);
                });
                
                // Add PPN to taxes and charges
                if (total_ppn != 0) {
                    let ppn_row = frm.add_child('taxes');
                    ppn_row.charge_type = 'Actual';
                    ppn_row.account_head = company.ppn_account;
                    ppn_row.description = 'PPN';
                    ppn_row.tax_amount = total_ppn; 
                    ppn_row.tipe_pajak = "PPN"               
                }
                
                // Add PPh to taxes and charges
                if (total_pph != 0) {
                    let pph_row = frm.add_child('taxes');
                    pph_row.charge_type = 'Actual';
                    pph_row.account_head = company.pph_account;
                    pph_row.description = 'PPh';
                    pph_row.tax_amount = total_pph;
                    pph_row.tipe_pajak = "PPH"             
                }
                
                frm.refresh_field('items');
                frm.refresh_field('taxes');
            }
        }
    });
}

// Child table: Non Voucher Match
frappe.ui.form.on('Non Voucher Match', {
    form_render: function(frm, cdt, cdn) {
        // Set query filter for COA field
        frm.fields_dict['non_voucher_match'].grid.get_field('coa').get_query = function(doc) {
            return {
                filters: {
                    'company': doc.company,
                    'is_group': 0
                }
            };
        };
    },
    
    dpp: function(frm, cdt, cdn) {
        calculate_non_voucher_row(frm, cdt, cdn);
    },
    
    ppn: function(frm, cdt, cdn) {
        calculate_non_voucher_row(frm, cdt, cdn);
    },
    
    pph: function(frm, cdt, cdn) {
        calculate_non_voucher_row(frm, cdt, cdn);
    },
    
    persen_ppn: function(frm, cdt, cdn) {
        calculate_non_voucher_row(frm, cdt, cdn);
    },
    
    persen_pph: function(frm, cdt, cdn) {
        calculate_non_voucher_row(frm, cdt, cdn);
    }
});

function calculate_non_voucher_row(frm, cdt, cdn) {
    calculate_ppn_from_percentage(frm, cdt, cdn)
    calculate_pph_from_percentage(frm, cdt, cdn)
    let row = locals[cdt][cdn];
    
    // Calculate DPP Nilai Lainnya = DPP * 11 / 12
    if (row.dpp) {
        row.dpp_nilai_lainnya = (row.dpp * 11) / 12;
    }
    
    // Calculate Total = DPP + PPN + PPH
    row.total = (row.dpp || 0) + (row.ppn || 0) + (row.pph || 0);
    
    frm.refresh_field('non_voucher_match');
}

function calculate_ppn_from_percentage(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    
    if (row.persen_ppn && row.dpp) {
        row.ppn = (row.dpp * row.persen_ppn) / 100;
    }
}

function calculate_pph_from_percentage(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    
    if (row.persen_pph && row.dpp) {
        row.pph = (row.dpp * row.persen_pph) / 100 * -1;
    }
}