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
        let totals = lembar_total = 0
        for (const item of frm.doc.saham || []) {
            let agio_amount = flt(item.agio_rate) * flt(item.qty)
            let saham_amount = flt(item.rate) * flt(item.qty)
            item.amount = saham_amount + agio_amount
            totals += flt(item.amount)
            lembar_total += flt(item.qty)
        }

        frm.set_value("grand_total", totals)
        frm.set_value("total_lembar_saham", lembar_total)
    }
});


frappe.ui.form.on("Detail Form Saham", {
    qty(frm){
        frm.trigger("calculate_total")
    },
    rate(frm){
        frm.trigger("calculate_total")
    },
    agio_rate(frm){
        frm.trigger("calculate_total")
    }
});