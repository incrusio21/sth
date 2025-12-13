frappe.ui.form.on('Pengakuan Pembelian TBS', {
    get_data: function (frm) {
        if (!frm.doc.nama_supplier) {
            frappe.msgprint(__('Please select a supplier first'));
            return;
        }
        frm.call("get_timbangan")
            .then((res) => {
                frappe.model.sync(res);
                frm.refresh();
            })
    }
});
