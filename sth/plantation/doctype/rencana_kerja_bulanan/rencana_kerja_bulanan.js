// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Rencana Kerja Bulanan", {
	refresh(frm) {
        frm.trigger("set_query_field")
	},
    set_query_field(frm){
        frm.set_query("unit", function(doc){
            return{
                filters: {
                    company: doc.company
                }
            }
        })
    },
    from_date(frm){
        frm.set_value("to_date", 
            frm.doc.from_date ? 
            sth.datetime.month_end(frm.doc.from_date) : ""
        )
    }
});
