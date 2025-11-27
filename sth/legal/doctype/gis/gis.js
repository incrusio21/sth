// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("GIS", {
	// refresh(frm) {

	// },
    lahan_inti(frm){
        frm.trigger("calculate_total_lahan")
    },
    lahan_plasma(frm){
        frm.trigger("calculate_total_lahan")
    },
    calculate_total_lahan(frm){
        frm.set_value("total_lahan", flt(frm.doc.lahan_inti) + flt(frm.doc.lahan_plasma))
    }
});
