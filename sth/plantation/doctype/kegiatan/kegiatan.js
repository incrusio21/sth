// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Kegiatan", {
// 	refresh(frm) {

// 	},
// });

frappe.ui.form.on("Kegiatan Company", {
	persentase_premi(frm, cdt, cdn) {
        let item = locals[cdt][cdn]
        frappe.model.set_value(cdt, cdn, "min_basis_premi", item.have_premi ? flt(item.volume_basis * (100 + item.persentase_premi) / 100) : 0)
	},
});