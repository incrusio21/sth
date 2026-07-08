// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pemeriksaan Vibrasi", {
    onload(frm) {
        frm.set_df_property("gearbox", "cannot_add_rows", "true")
        frm.set_df_property("generator", "cannot_add_rows", "true")
    },
});

frappe.ui.form.on("Detail Vibrasi Turbine", {
    turbine_add(frm, dt, dn) {

        const row = locals[dt][dn];

        ["gearbox", "generator"].forEach(t => {
            frm.add_child(t, {
                "jam": row.jam,
                "beban": row.beban
            })
            frm.refresh_field(t)
        })
    },

    jam(frm, dt, dn) {
        frm.script_manager.trigger("sync_jam_dan_beban", dt, dn)
    },

    beban(frm, dt, dn) {
        frm.script_manager.trigger("sync_jam_dan_beban", dt, dn)
    },

    sync_jam_dan_beban(frm, dt, dn) {
        const data = locals[dt][dn];

        ["gearbox", "generator"].forEach(t => {
            frm.doc[t][data.idx - 1].jam = data.jam
            frm.doc[t][data.idx - 1].beban = data.beban

            frm.refresh_field(t)
        });
    }
});
