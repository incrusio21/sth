
frappe.ui.form.on("Stock Reconciliation",{
    onload:function(frm){
        const original_link_formatter = frappe.form.formatters.Link;

        frappe.form.formatters.Link = function(value, docfield, options, doc) {
            // Tampilkan plain text untuk Procurement Settings
            if (docfield) {
                return value || "";
            }
            // Doctype lain tetap pakai formatter asli
            return original_link_formatter(value, docfield, options, doc);
        };
        frm.fields_dict["items"].grid.refresh();
    },
    refresh(frm) {
        set_unit_filter(frm);
    },
    company(frm) {
        set_unit_filter(frm);
    }
});

frappe.ui.form.on('Stock Reconciliation Item', {

    retain_amount: function(frm, cdt, cdn) {
        let item = locals[cdt][cdn];
        if (item.retain_amount) {
            // Clear valuation_rate when retain_amount is checked
            // It will be calculated from current_amount
            calculate_valuation_from_amount(frm, cdt, cdn);
        }
    },
    
    current_amount: function(frm, cdt, cdn) {
        let item = locals[cdt][cdn];
        if (item.retain_amount) {
            calculate_valuation_from_amount(frm, cdt, cdn);
        }
    },
    
    qty: function(frm, cdt, cdn) {
        let item = locals[cdt][cdn];
        if (item.retain_amount) {
            calculate_valuation_from_amount(frm, cdt, cdn);
        }
    },
    
    valuation_rate: function(frm, cdt, cdn) {
        let item = locals[cdt][cdn];
        // If retain_amount is checked, prevent manual valuation_rate changes
        if (item.retain_amount && item.current_amount && item.qty) {
            // Recalculate to override manual changes
            calculate_valuation_from_amount(frm, cdt, cdn);
        }
    }
});

function calculate_valuation_from_amount(frm, cdt, cdn) {
    let item = locals[cdt][cdn];
    
    if (item.retain_amount && item.current_amount && item.qty && item.qty != 0) {
        let valuation_rate = flt(item.current_amount / item.qty, 
                                precision('valuation_rate', item));
        
        frappe.model.set_value(cdt, cdn, 'valuation_rate', valuation_rate);
        
        // Calculate amount (qty * valuation_rate)
        let amount = flt(item.qty * valuation_rate, precision('amount', item));
        frappe.model.set_value(cdt, cdn, 'amount', amount);
        
    } else if (item.retain_amount && (!item.current_amount || !item.qty)) {
        frappe.model.set_value(cdt, cdn, 'valuation_rate', 0);
        frappe.model.set_value(cdt, cdn, 'amount', 0);
    }
}

function set_unit_filter(frm) {
    if (frm.doc.company) {
        frm.set_query('unit', function() {
            return {
                filters: {
                    'company': frm.doc.company
                }
            };
        });
    } else {
        frm.set_query('unit', function() {
            return {};
        });
    }
}