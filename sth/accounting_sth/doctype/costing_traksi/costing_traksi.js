frappe.ui.form.on("Costing Traksi", {
    refresh(frm) {
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__("Ambil Data"), () => {
                frm.call_ambil_data();
            }, __("Tools"));
        }
    },

    call_ambil_data(frm) {
        if (!frm.doc.periode_dari || !frm.doc.periode_sampai) {
            frappe.msgprint(__("Harap isi Periode Dari dan Periode Sampai terlebih dahulu."));
            return;
        }

        frappe.show_progress(__("Mengambil data..."), 0, 100);

        Promise.all([
            frappe.call({
                method: "sth.accounting_sth.doctype.costing_traksi.costing_traksi.get_pengeluaran_barang_traksi",
                args: {
                    periode_dari: frm.doc.periode_dari,
                    periode_sampai: frm.doc.periode_sampai
                }
            }),
            frappe.call({
                method: "sth.accounting_sth.doctype.costing_traksi.costing_traksi.get_bkmt_traksi",
                args: {
                    periode_dari: frm.doc.periode_dari,
                    periode_sampai: frm.doc.periode_sampai
                }
            })
        ]).then(([pb_res, bkmt_res]) => {
            frappe.hide_progress();

            // Isi tabel Pengeluaran Barang
            frm.clear_table("pengeluaran_barang_items");
            (pb_res.message || []).forEach(row => {
                let d = frm.add_child("pengeluaran_barang_items");
                d.no_dokumen = row.no_dokumen;
                d.total = row.total;
            });

            // Isi tabel BKM Traksi
            frm.clear_table("bkmt_items");
            (bkmt_res.message || []).forEach(row => {
                let d = frm.add_child("bkmt_items");
                d.no_dokumen = row.no_dokumen;
                d.total = row.total;
            });

            // Hitung total
            let total_pb = (pb_res.message || []).reduce((s, r) => s + (r.total || 0), 0);
            let total_bkmt = (bkmt_res.message || []).reduce((s, r) => s + (r.total || 0), 0);

            frm.set_value("total_pengeluaran_barang", total_pb);
            frm.set_value("total_bkmt", total_bkmt);
            frm.set_value("grand_total", total_pb + total_bkmt);

            frm.refresh_fields();
            frappe.show_alert({ message: __("Data berhasil diambil"), indicator: "green" });
        });
    }
});
