// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Purchase Order", {
    refresh(frm){
        frm.set_query("kegiatan", "items", function (doc) {
			return {
				filters: {
					is_group: 0,
				},
			};
		});
    }
});

frappe.ui.form.on("Purchase Order Item", {
    kegiatan(frm, cdt, cdn){
        let item = locals[cdt][cdn]

        frappe.call({
            method: "sth.legal.custom.purchase_order.get_kegiatan_item",
            args: {
                "kegiatan": item.kegiatan
            },
            callback: function (r) {
                frappe.model.set_value(cdt, cdn, r.message)
            }
        })
    }
})