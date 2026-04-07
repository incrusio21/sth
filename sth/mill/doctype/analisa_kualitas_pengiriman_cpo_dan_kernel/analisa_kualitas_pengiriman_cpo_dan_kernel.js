// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Analisa Kualitas Pengiriman CPO dan KERNEL", {
    setup(frm) {
        frm.set_query("ticket_number", (doc) => {
            return {
                query: frappe.model.get_server_module_name(doc.doctype) + ".get_filter_ticket",
                filters: {
                    tipe: doc.tipe
                }
            }
        })
    },
});
