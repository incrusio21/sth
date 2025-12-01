// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Purchase Order", {
    set_query_field(frm) {
        frm.set_query("kegiatan", "items", function (doc) {
			return {
				filters: {
					is_group: 0,
				},
			};
		});

        if (frm.doc.docstatus == 1 && !["Closed", "Delivered"].includes(frm.doc.status)) {
            if (
                frm.doc.status !== "Closed" &&
                flt(frm.doc.per_received) < 100 &&
                frm.doc.__onload.order_revisions
            ) {
                frm.add_custom_button(
                    __("Purchase Order Revision"), () => {
                        frappe.model.open_mapped_doc({
                            method: "sth.legal.custom.purchase_order.make_purchase_order_revision",
                            frm: cur_frm,
                            freeze_message: __("Creating Purchase Order Revision ..."),
                        });
                    },
                    __("Create")
                );
            }
        }
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