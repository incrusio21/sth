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
    },
});
