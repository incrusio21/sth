// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Anggaran Dasar", {
	refresh(frm) {

	},
    calculate_total(frm){
        let totals = 0
        for (const item of frm.doc.saham || []) {
            item.amount = flt(item.rate) * flt(item.qty)
            totals += flt(item.amount)
        }

        frm.set_value("grand_total", totals)
    }
});

frappe.ui.form.on("Detail Form Saham", {
    qty(frm){
        frm.trigger("calculate_total")
    },
    rate(frm){
        frm.trigger("calculate_total")
    }
});