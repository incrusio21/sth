frappe.ui.form.on('Supplier', {
    onload: function(frm) {
        if (frm.is_new() && !frm.doc.kode_supplier) {
            generate_kode_supplier(frm);
        }
    },
});

function generate_kode_supplier(frm) {
    frappe.call({
        method: 'sth.overrides.supplier.get_next_supplier',
        callback: function(r) {
            if (r.message) {
                frm.set_value('kode_supplier', r.message);
            }
        }
    });
}