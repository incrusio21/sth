// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

sth.plantation.setup_budget_controller()

frappe.ui.form.on("Budget Traksi Tahunan", {
    total_km_hm(frm){
        cur_frm.cscript.after_calculate_grand_total()

        frm.refresh_fields()
    },
    kode_kendaraan(frm){
        frappe.call({
            
        })
    }
});

sth.plantation.BudgetTraksiTahunan = class BudgetTraksiTahunan extends sth.plantation.BudgetController {
    refresh(doc) {
        super.refresh(doc)
    }

    set_query_field(frm){
        this.frm.set_query("kode_kendaraan", function(doc){
            if(!doc.divisi){
                frappe.throw("Please Select Divisi First")
            }

		    return{
		        filters: {
                    divisi: doc.divisi
                }
		    }
		})
    }

    after_calculate_grand_total(){
        this.frm.doc.rp_kmhm = flt(
            this.frm.doc.grand_total / this.frm.doc.total_km_hm, 
            precision("rp_kmhm", this.frm.doc)
        );
    }
}

cur_frm.script_manager.make(sth.plantation.BudgetTraksiTahunan);