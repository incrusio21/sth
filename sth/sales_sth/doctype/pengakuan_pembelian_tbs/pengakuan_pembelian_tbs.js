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
    },

    jarak(frm) {
        const jarak = frm.doc.jarak
        if (jarak) {
            const method = frappe.model.get_server_module_name(frm.doctype) + "." + "get_rate"
            frappe
                .xcall(method, { jarak })
                .then((res) => {
                    frm.set_value("harga", res + frm.doc.subsidi_angkut)
                })
        }
    },

    subsidi_angkut(frm) {
        frm.set_value("harga", frm.doc.harga + frm.doc.subsidi_angkut)
    }
});
