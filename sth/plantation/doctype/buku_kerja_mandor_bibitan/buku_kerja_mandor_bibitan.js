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
});
