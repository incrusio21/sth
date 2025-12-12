frappe.ui.form.on('Pengakuan Pembelian TBS', {
    get_data: function(frm) {
        if (!frm.doc.nama_supplier) {
            frappe.msgprint(__('Please select a supplier first'));
            return;
        }

        frappe.call({
            method: 'sth.sales_sth.doctype.pengakuan_pembelian_tbs.pengakuan_pembelian_tbs.get_purchase_order_items',
            args: {
                nama_supplier: frm.doc.nama_supplier
            },
            callback: function(r) {
                if (r.message && r.message.length > 0) {
                    frm.clear_table('items'); 
                    
                    r.message.forEach(function(item) {
                        let row = frm.add_child('items');
                        row.item_code = item.item_code;
                        row.item_name = item.item_name;
                        row.qty = item.qty;
                        row.rate = item.rate;
                        row.total = item.total;
                    });
                    
                    frm.refresh_field('items');
                    frappe.msgprint(__('Successfully loaded {0} items', [r.message.length]));
                } else {
                    frappe.msgprint(__('No Purchase Order items found for this supplier'));
                }
            }
        });
    }
});