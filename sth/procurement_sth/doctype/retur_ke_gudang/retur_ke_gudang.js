// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Retur Ke Gudang", {
    setup(frm) {
        frm.set_query("gudang", function (doc) {
            return {
                filters: {
                    is_group: 0,
                    company: doc.pemilik
                }
            }
        })
    },

    calculate_retur(frm) {
        let jumlah = 0

        frm.doc.items.forEach((row) => {
            jumlah += row.jumlah
        })
        frm.set_value("jumlah_retur", jumlah)
    },

    no_pengeluaran(frm) {
        if (!frm.doc.no_pengeluaran) {
            return
        }

        frm.call("set_items").then((res) => {
            frappe.model.sync(res)
            frm.refresh()
        })
    }
});

frappe.ui.form.on("Retur Items", {
    jumlah(frm, cdt, cdn) {
        frm.trigger('calculate_retur')
    }
})
