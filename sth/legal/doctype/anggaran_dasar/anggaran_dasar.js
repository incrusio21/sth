// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Anggaran Dasar", {
	refresh(frm) {
        for (const table of ["saham", "pengurus", "kriteria"]) {
            frm.set_df_property(table, "cannot_add_rows", true);
            
            frm.fields_dict[table].grid.add_custom_button("Add Row", () => {
                if(!frm.doc[`akta_saham`]){
                    frappe.throw("Plase set Akta first.")
                }
                
                frm.add_child(table, {
                    akta: frm.doc[`akta_saham`],
                });

                frm.refresh_fields(table)
            })
		}
        
        frm.set_query(`akta_saham`, (doc) => {
            return {
                filters: {
                    company: ["=", doc.company]
                }
            }
        })
        
        
	},
    calculate_total(frm){
        let totals = 0
        for (const item of frm.doc.saham || []) {
            item.amount = flt(item.rate) * flt(item.qty)
            totals += flt(item.amount)
        }

        frm.set_value("grand_total", totals)
    }
});


frappe.ui.form.on("Detail Form Saham", {
    qty(frm){
        frm.trigger("calculate_total")
    },
    rate(frm){
        frm.trigger("calculate_total")
    }
});