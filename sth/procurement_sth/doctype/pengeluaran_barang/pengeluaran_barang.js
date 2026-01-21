// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pengeluaran Barang", {
    setup(frm) {
        frm.set_query("no_permintaan_pengeluaran", function (doc) {
            return {
                filters: {
                    pt_pemilik_barang: doc.pt_pemilik_barang,
                    docstatus: 1,
                    outgoing: ["<", 100],
                    status: ["!=", "Closed"]
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
        frm.set_df_property("items", "cannot_add_rows", true)
    },

    no_permintaan_pengeluaran(frm) {
        if (!frm.doc.no_permintaan_pengeluaran) {
            return
        }

        frm.call("set_items").then((res) => {
            frappe.model.sync(res)
            frm.refresh()
        })
    }
});
