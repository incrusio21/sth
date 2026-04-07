// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Penginputan Stock By Product", {
    nama_barang(frm) {
        if (!frm.doc.nama_barang) return
        frm.call("get_stock").then(() => {
            frm.refresh()
        })
    },

    input_dipakai_pabrik(frm) {
        frm.trigger('calculate_stock_akhir')
    },

    calculate_stock_akhir(frm) {
        const stock_akhir = frm.doc.stock_awal + frm.doc.produksi - frm.doc.pengiriman - frm.doc.input_dipakai_pabrik
        frm.set_value("stock_akhir", stock_akhir)
    }
});
