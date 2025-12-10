// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Anggaran Dasar", {
	refresh(frm) {
        for (const table of ["saham", "pengurus", "kriteria"]) {
            frm.set_df_property(table, "cannot_add_rows", true);

			frm.set_query(`akta_${table}`, (doc) => {
                return {
                    filters: {
                        company: ["=", doc.company]
                    }
                }
            })
            
            frm.fields_dict[table].grid.add_custom_button("Add Row", () => {
                if(!frm.doc[`akta_${table}`]){
                    frappe.throw("Plase set Akta first.")
                }
                
                frm.add_child(table, {
                    akta: frm.doc[`akta_${table}`],
                });
    
                frm.refresh_fields(table)
            })
		}
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