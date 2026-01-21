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
        if (frm.doc.docstatus == 1 && !["Barang Telah Dikeluarkan", "Closed"].includes(frm.doc.status)) {
            frm.add_custom_button("Closed", function () {

                frappe.confirm(
                    'Apakah anda yakin ingin menutup dokumen ini?',
                    () => {
                        const method = frappe.model.get_server_module_name(frm.doctype) + ".close_status"
                        frappe.xcall(method, { name: frm.docname }).then(() => {
                            frm.reload_doc()
                            frappe.show_alert({
                                message: __('Document has been closed'),
                                indicator: 'green'
                            });
                        })
                    },
                    null
                );
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
