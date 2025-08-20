// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

sth.plantation.setup_budget_controller()

// frappe.ui.form.on("Budget Supervisi Tahunan", {
// 	refresh(frm) {

// 	},
// });

sth.plantation.BudgetSupervisiTahunan = class BudgetSupervisiTahunan extends sth.plantation.BudgetController {
    refresh(doc) {
        super.refresh(doc)
        this.skip_table_amount.push("distribusi")
    }

    item(doc, cdt, cdn){
        if(cdt != "Detail Budget Distribusi"){
            super.item(doc, cdt, cdn)
        }else{
            let item = frappe.get_doc(cdt, cdn)
            frappe.model.set_value(cdt, cdn, "rate", flt(doc.grand_total / doc.jml_hk, precision("rate", item)))
        }
    }

    after_calculate_grand_total(){
        let doc = this.frm.doc
        // biaya per tahun = grand total / qty table bibitan atau perawatan
        for (const item of doc.distribusi) {
            item.rate = flt(doc.grand_total / doc.jml_hk, precision("rate", item))
        }
        this.calculate_item_values("distribusi")
    }
}

cur_frm.script_manager.make(sth.plantation.BudgetSupervisiTahunan);