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

    show_calculate_pyramid_dialog(frm) {
        const d = frappe.ui.Dialog({
            title: __('Hitung Volume Limas'),
            fields: [
                {
                    label: __('Luas Alas (La)'),
                    fieldname: 'base_area',
                    fieldtype: 'Float',
                    reqd: 1,
                    description: __('Masukkan luas alas limas')
                },
                {
                    label: __('Tinggi (t)'),
                    fieldname: 'height',
                    fieldtype: 'Float',
                    reqd: 1,
                    description: __('Masukkan tinggi tegak limas')
                },
                {
                    fieldtype: 'Section Break'
                },
                {
                    label: __('Hasil Volume'),
                    fieldname: 'volume_result',
                    fieldtype: 'Float',
                    read_only: 1
                }
            ],
            primary_action_label: __('Hitung'),
            primary_action(values) {

            }
        });

        d.show();
    }

});

frappe.ui.form.on("Palm Kernel Bunker Detail", {
    titik_bunker(frm, dt, dn) {
        const row = locals[dt][dn]
        frappe.model.set_value(dt, dn, "hasil_titik_sounding", row.titik_bunker - frm.doc.tinggi_lubang_ukur)
    },
});

frappe.ui.form.on("Sounding Average Detail", {
    hitung_limas(frm, dt, dn) {
        const row = locals[dt][dn]
        if (row.total_hitungan <= 0) {

        }
    }
});
