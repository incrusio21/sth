frappe.ui.form.on('Item', {
    onload: function(frm) {
        if (frm.is_new() && !frm.doc.item_code) {
            generate_item_code(frm);
        }
    },
    
    refresh: function(frm) {
        if (frm.is_new()) {
            frm.add_custom_button(__('Generate Item Code'), function() {
                generate_item_code(frm);
            });
        }
    }
});

function generate_item_code(frm) {
    frappe.call({
        method: 'sth.overrides.item.get_next_item_code',
        callback: function(r) {
            if (r.message) {
                frm.set_value('item_code', r.message);
            }
        }
    });
}