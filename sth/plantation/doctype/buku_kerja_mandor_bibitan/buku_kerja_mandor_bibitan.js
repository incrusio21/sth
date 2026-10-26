// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Buku Kerja Mandor Bibitan", {
    setup(frm) {
        frm.set_query("kegiatan", function (doc) {
            return {
                filters: {
                    company: ["=", doc.company],
                }
            }
        })

        frm.set_query("item", "material", function (doc) {
            return {
                query: 'sth.controllers.queries.material_kegiatan_query',
                filters: {
                    kegiatan: ["=", doc.kegiatan],
                }
            }
        })
    },

    refresh(frm) {
        if (frm.doc.docstatus == 0) return

        frm.add_custom_button(__("BKM Perawatan"), () => {
            frappe.route_options = {
                voucher_type: frm.doc.doctype,
                voucher_no: frm.doc.name,
            };
            frappe.set_route("List", "Buku Kerja Mandor Perawatan");
        }, __("View"));
    },
});
