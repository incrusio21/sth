// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Permintaan Pengeluaran Barang", {
    setup(frm) {
        frm.set_query("gudang", function (doc) {
            return {
                filters: {
                    is_group: 0,
                    company: doc.pt_pemilik_barang,
                }
            }
        })

        frm.set_query("sub_unit", "items", function (doc) {
            return {
                filters: {
                    company: doc.pt_pemilik_barang,
                }
            }
        })

        frm.set_query("blok", "items", function (doc, dt, dn) {
            const child = locals[dt][dn]

            return {
                filters: {
                    unit: child.sub_unit,
                }
            }
        })
    },

    refresh(frm) {
        if (frm.doc.docstatus == 1 && frm.doc.status != "Barang Telah Dikeluarkan") {
            frm.add_custom_button("Closed", function () {
                if (frm.doc.status == "Closed") {
                    return
                }
            })
        }
    },

    sub_unit(frm) {
        if (!frm.doc.sub_unit) {
            return
        }
        // frappe.xcall("frappe.client.get_value", {
        //     doctype: "Blok",
        //     fieldname: ["name"],
        //     filters: {
        //         unit: frm.doc.sub_unit
        //     }
        // }).then((res) => {
        //     frm.set_value("blok", res.name)
        // })
    }
});
