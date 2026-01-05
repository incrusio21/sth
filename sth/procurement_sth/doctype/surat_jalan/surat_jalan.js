// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Surat Jalan", {
    setup(frm) {
        const wh_fields = ["gudang_tujuan", "gudang_asal"]
        wh_fields.forEach(field => {
            frm.set_query(field, function (doc) {
                return {
                    filters: {
                        is_group: 0,
                        company: doc.company
                    }
                }
            })
        });

        frm.set_query("unit", function (doc) {
            return {
                filters: {
                    company: doc.company
                }
            }
        })
    },

    refresh(frm) {
        if (frm.doc.docstatus == 0) {
            frm.add_custom_button("Purchase Order", function () {
                frm.events.open_dialog_get_items(frm, "purchase")
            }, __("Get Items From"))

            frm.add_custom_button("Material", function () {
                frm.events.open_dialog_get_items(frm, "material")
            }, __("Get Items From"))
        }
    },

    open_dialog_get_items(frm, type) {
        const base = frappe.model.get_server_module_name(frm.doctype)
        let method = base + ".get_items_from_doctype"
        if (type == "purchase") {

        }

    }
});
