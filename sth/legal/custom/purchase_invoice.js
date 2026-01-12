// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Purchase Invoice", {
    refresh(frm) {
        if(frm.doc.docstatus == 0){
            frm.add_custom_button(
                __("BAPP"),
                function () {
                    erpnext.utils.map_current_doc({
                        method: "sth.legal.doctype.bapp.bapp.make_purchase_invoice",
                        source_doctype: "BAPP",
                        target: frm,
                        setters: {
                            supplier: frm.doc.supplier || undefined,
                            posting_date: undefined,
                        },
                        get_query_filters: {
                            docstatus: 1,
                            status: ["not in", ["Closed", "Completed", "Return Issued"]],
                            company: frm.doc.company,
                        },
                    });
                },
                __("Get Items From")
            );
        }
    },
})