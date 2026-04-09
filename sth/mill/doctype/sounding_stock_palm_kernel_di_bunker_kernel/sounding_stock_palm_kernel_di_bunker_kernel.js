// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sounding Stock Palm Kernel di Bunker Kernel", {
    refresh(frm) {

    },
});

frappe.ui.form.on("Palm Kernel Bunker Detail", {
    titik_bunker(frm, dt, dn) {
        const row = locals[dt][dn]
        frappe.model.set_value(dt, dn, "hasil_titik_sounding", row.titik_bunker - frm.doc.tinggi_lubang_ukur)
    },
});
