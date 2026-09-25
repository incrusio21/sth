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

    onload(frm) {
        if (!frm.is_new()) return

        new frappe.ui.Scanner({
            dialog: true,
            multiple: false,
            on_scan(data) {
                frm.events.apply_qr_pabrik(frm, data)
            },
        })

        frm.trigger('get_location')
    },

    apply_qr_pabrik(frm, data) {
        // Isi QR pabrik dibuat Mill Master: { pabrik, unit, latitude, longitude }
        const text = data && data.result && data.result.text
        if (!text) return

        let scan_data
        try {
            scan_data = JSON.parse(text)
        } catch (e) {
            scan_data = null
        }

        if (!scan_data || !scan_data.pabrik) {
            frappe.msgprint(__("QR tidak dikenali. Pastikan yang discan adalah QR Pabrik."))
            return
        }

        frm.set_value("pabrik", scan_data.pabrik)
        frm.set_value("pabrik_latitude", scan_data.latitude)
        frm.set_value("pabrik_longitude", scan_data.longitude)

        frm.set_value("tanggal_scan", frappe.datetime.get_today())
        frm.set_value("jam_scan", moment().format('HH:mm:ss'))
        frm.set_value("user_scan", frappe.session.user)
    },

    get_location(frm) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                frm.set_value("latitude", position.coords.latitude)
                frm.set_value("longitude", position.coords.longitude)
            },
            (err) => {
                frappe.msgprint(err.message);
            }
        );
    },

    refresh(frm) {
        frm.set_df_property("hasil_titik_sounding", "cannot_add_rows", true)
        sth.sounding.buat_tombol_hitung_ulang(frm, { rekap: __("rekap Palm Kernel") })
    },

    get_stock(frm) {
        frm.call('get_stock').then(() => {
            frm.refresh()
            frm.dirty()
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
                    label: __('Volume Liter'),
                    fieldname: 'berat_kg',
                    fieldtype: 'Float',
                    read_only: 1,
                    default: 0
                }
            ],
            primary_action_label: __('Hitung Limas'),
            primary_action(values) {
                const result = values.perkiraan * values.density * values.berat_kg
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
