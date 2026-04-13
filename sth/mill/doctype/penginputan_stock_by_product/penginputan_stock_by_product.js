// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Penginputan Stock By Product", {
    setup(frm) {
        frm.set_query("unit", (doc) => {
            return {
                filters: {
                    company: doc.company,
                }
            }
        })

        frm.set_query("gudang", (doc) => {
            return {
                filters: {
                    unit: doc.unit,
                    is_group: 0,

                }
            }
        })
    },

    unit(frm) {
        if (!frm.doc.unit) return
        frappe.db.get_value("Warehouse", { "unit": frm.doc.unit, "central": 1 }, "name", (res) => {
            frm.set_value("gudang", res.name)
        })
    },

    get_data(frm) {
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
