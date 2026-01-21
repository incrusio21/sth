// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Retur Ke Supplier", {
    setup(frm) {
        frm.set_query("no_dokumen_penerimaan", (doc) => {
            return {
                filters: {
                    set_warehouse: doc.gudang,
                    docstatus: 1,
                    status: ["not in", ["Return", "Return Issued"]],

                }
            }
        })

        frm.set_query("gudang", (doc) => {
            return {
                filters: {
                    is_group: 0,
                }
            }
        })
    },
    refresh(frm) {
        frm.set_df_property("items", "cannot_add_rows", true)
    },

    no_dokumen_penerimaan(frm) {
        if (!frm.doc.no_dokumen_penerimaan) {
            return
        }

        frm.call("get_items", { freeze: true, freeze_message: "Getting data..." }).then((res) => {
            frappe.model.sync(res)
            frm.refresh()
            frm.trigger('calculate_jumlah_retur')
        })
    },

    calculate_jumlah_retur(frm) {
        let jumlah = 0
        for (const row of frm.doc.items) {
            jumlah += row.jumlah
        }
        frm.set_value("jumlah_retur", jumlah)
    }
});


frappe.ui.form.on("Retur Supplier Item", {
    jumlah(frm, dt, dn) {
        // let row = locals[dt][dn]
        frm.trigger('calculate_jumlah_retur')
    }
})