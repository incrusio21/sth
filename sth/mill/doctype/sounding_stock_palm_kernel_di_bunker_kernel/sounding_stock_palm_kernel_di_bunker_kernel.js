// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sounding Stock Palm Kernel di Bunker Kernel", {
    setup(frm) {
        frm.set_query("nama_kompartemen_bunker", "ukuran_detail", (doc) => {
            return {
                filters: {
                    pabrik: doc.pabrik
                }
            }
        })
    },

    refresh(frm) {
        frm.set_df_property("hasil_titik_sounding", "cannot_add_rows", true)
    },

    get_stock(frm) {
        frm.call('get_stock').then(() => {
            frm.refresh()
        })
    },

    show_calculate_pyramid_dialog(doc, row) {
        const dialog = new frappe.ui.Dialog({
            title: __('Hitung Volume Limas'),
            fields: [
                {
                    label: __('Perkiraan'),
                    fieldname: 'perkiraan',
                    fieldtype: 'Float',
                    reqd: 1,
                    default: 0
                },
                {
                    label: __('Berat Jenis/Density'),
                    fieldname: 'density',
                    fieldtype: 'Float',
                    reqd: 1,
                    default: 0,
                    change: (el) => {
                        const val = flt(el.target.value)
                        const method = frappe.model.get_server_module_name(doc.doctype) + ".get_berat_limas"
                        frappe.xcall(method, {
                            density: val, kompartemen: row.kompartemen, pabrik: doc.pabrik
                        }).then((res) => {
                            dialog.set_value('berat_kg', res)
                        })
                    }
                },
                {
                    label: __('Berat (Kg/M3)'),
                    fieldname: 'berat_kg',
                    fieldtype: 'Float',
                    read_only: 1,
                    default: 0
                }
            ],
            primary_action_label: __('Hitung Limas'),
            primary_action(values) {
                const result = values.perkiraan * values.berat_kg
                frappe.model.set_value(row.doctype, row.name, 'netto', result)
                dialog.hide()
            }
        });

        dialog.show();
    }

});

frappe.ui.form.on("Palm Kernel Bunker Detail", {
    titik_bunker(frm, dt, dn) {
        const row = locals[dt][dn]
        frappe.model.set_value(dt, dn, "hasil_titik_sounding", row.titik_bunker - frm.doc.tinggi_lubang_ukur)
    },
});

frappe.ui.form.on("Ukuran Volume Sounding Bunker", {
    hitung_limas(frm, dt, dn) {
        const row = locals[dt][dn]
        if (row.ukuran <= 0) {
            frm.events.show_calculate_pyramid_dialog(frm.doc, row)
        }
    }
});
