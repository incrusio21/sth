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
                    central: 1
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

        frm.call("get_data", { freeze: true, freeze_message: "Getting data..." }).then((res) => {
            frappe.run_serially([
                () => frm.refresh(),
                () => frm.trigger('set_available_stock'),
            ])
        })
    },

    gudang(frm) {
        frm.trigger('set_available_stock')
    },

    set_available_stock(frm) {
        for (const item of frm.doc.items) {
            if (!frm.doc.gudang || !item.kode_barang) {
                frappe.model.set_value(item.doctype, item.name, "stock_saat_ini", 0)
            } else {
                frappe.xcall("sth.api.get_stock_item", { item_code: item.kode_barang, warehouse: frm.doc.gudang })
                    .then((res) => {
                        frappe.model.set_value(item.doctype, item.name, "stock_saat_ini", res)
                    })
            }
        }
    }

    // calculate_jumlah_retur(frm) {
    //     let jumlah = 0
    //     for (const row of frm.doc.items) {
    //         jumlah += row.jumlah
    //     }
    //     frm.set_value("jumlah_retur", jumlah)
    // }
});


frappe.ui.form.on("Retur Supplier Item", {
    jumlah(frm, dt, dn) {
        // let row = locals[dt][dn]
        frm.trigger('calculate_jumlah_retur')
    }
})


frappe.form.link_formatters['Item'] = function (value, doc) {
    return doc.kode_barang || doc.nama_barang
}
