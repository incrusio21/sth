// Client Script for Stock Reconciliation Item

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