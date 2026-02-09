// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Permintaan Pengeluaran Barang", {
    setup(frm) {
        frm.set_query("gudang", function (doc) {
            return {
                filters: {
                    is_group: 0,
                    company: doc.pt_pemilik_barang,
                    central: true
                }
            }
        })

        frm.set_query("kode_barang", "items", function (doc) {
            return {
                query: "sth.controllers.queries.get_items_query",
            }
        })

        frm.set_query("sub_unit", "items", function (doc) {
            const query = frappe.model.get_server_module_name(doc.doctype) + ".filter_divisi"
            return {
                query,
                filters: {
                    warehouse: doc.gudang,
                }
            }
        })

        frm.set_query("blok", "items", function (doc, dt, dn) {
            const child = locals[dt][dn]

            return {
                filters: {
                    divisi: child.sub_unit,
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
        if (!frm.is_new()) {
            if (frm.doc.persetujuan_1) {
                frm.set_df_property('persetujuan_1', 'read_only', 1);
            }
            if (frm.doc.persetujuan_2) {
                frm.set_df_property('persetujuan_2', 'read_only', 1);
            }
        }
    },
    onload(frm) {
        if (!frm.is_new()) {
            if (frm.doc.persetujuan_1) {
                frm.set_df_property('persetujuan_1', 'read_only', 1);
            }
            if (frm.doc.persetujuan_2) {
                frm.set_df_property('persetujuan_2', 'read_only', 1);
            }
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

frappe.ui.form.on('Permintaan Pengeluaran Barang Item', {
    kode_barang: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (frm.doc.gudang && row.kode_barang) {
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Bin',
                    filters: {
                        'warehouse': frm.doc.gudang,
                        'item_code': row.kode_barang
                    },
                    fieldname: ['actual_qty']
                },
                callback: function (r) {
                    if (r.message) {
                        frappe.model.set_value(cdt, cdn, 'jumlah_saat_ini', r.message.actual_qty || 0);
                    } else {
                        frappe.model.set_value(cdt, cdn, 'jumlah_saat_ini', 0);
                    }
                }
            });
        } else if (!frm.doc.gudang) {
            frappe.msgprint(__('Please select Gudang first'));
            frappe.model.set_value(cdt, cdn, 'kode_gudang', '');
        }
    }
});
