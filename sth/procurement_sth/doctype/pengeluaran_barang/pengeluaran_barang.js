// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pengeluaran Barang", {
    setup(frm) {
        frm.set_query("no_permintaan_pengeluaran", function (doc) {
            return {
                filters: {
                    pt_pemilik_barang: doc.pt_pemilik_barang
                }
            }
        })

        frm.set_query("gudang", function (doc) {
            return {
                filters: {
                    is_group: 0,
                    company: doc.pt_pemilik_barang
                }
            }
        })
    },
    refresh(frm) {

    },
});
