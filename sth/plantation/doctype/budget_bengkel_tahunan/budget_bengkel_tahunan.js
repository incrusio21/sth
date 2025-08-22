// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

sth.plantation.setup_budget_controller()

frappe.ui.form.on("Budget Bengkel Tahunan", {
	refresh(frm) {
        
	},
    jam_per_tahun(frm){
        cur_frm.cscript.after_calculate_grand_total()

        frm.refresh_fields()
    }
});

sth.plantation.BudgetBengkelTahunan = class BudgetBengkelTahunan extends sth.plantation.BudgetController {
    refresh(doc) {
        super.refresh(doc)
        this.skip_table_amount.push("distribusi")
    }

    set_query_field(){
        super.set_query_field()

        this.frm.set_query("kode_bengkel", function(doc){
            if(!doc.divisi){
                frappe.throw("Please Select Divisi First")
            }
		    return{
		        filters: {
                    divisi: doc.divisi
                }
		    }
		})

        this.frm.set_query("item", "distribusi", function(doc){
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

    item(doc, cdt, cdn){
        if(cdt != "Detail Budget Distribusi Traksi"){
            super.item(doc, cdt, cdn)
        }else{
            frappe.model.set_value(cdt, cdn, "rate", doc.rp_kmhm)
        }
    }

    after_calculate_grand_total(){
        let doc = this.frm.doc

        doc.rp_kmhm = this.frm.doc.grand_total / this.frm.doc.jam_per_tahun

        // biaya per tahun = grand total / qty table bibitan atau perawatan
        for (const item of doc.distribusi) {
            item.rate = doc.rp_kmhm
        }
        this.calculate_item_values("distribusi")
    }
}

cur_frm.script_manager.make(sth.plantation.BudgetBengkelTahunan);