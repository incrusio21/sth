// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Purchase Receipt", {
    setup(frm){
        sth.form.setup_fieldname_select(frm, "items")
    },
    refresh(frm){
        frm.set_query("purchase_type", () => {
            return {
                filters: {
                    document_type: frm.doctype
                }
            }
        })
		sth.form.setup_column_table_items(frm, frm.doc.purchase_type, "Purchase Receipt Item")
    },
    purchase_type(frm){
		sth.form.setup_column_table_items(frm, frm.doc.purchase_type, "Purchase Receipt Item")
    }
});