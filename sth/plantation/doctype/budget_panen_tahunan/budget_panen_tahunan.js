// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

sth.plantation.setup_budget_controller()

frappe.ui.form.on("Budget Panen Tahunan", {
	refresh(frm) {

	},
    divisi(frm){
        frm.cscript.clear_table(["tonase"])

        frm.cscript.add_blok_in_table("tonase", 
            { divisi: frm.doc.divisi }, 
            { "uom": frm.doc.uom }
        )
    }
});

sth.plantation.BudgetPanenTahunan = class BudgetPanenTahunan extends sth.plantation.BudgetController {
    refresh(doc) {
        super.refresh(doc)
        this.skip_table_amount.push("tonase")
    }
}

cur_frm.script_manager.make(sth.plantation.BudgetPanenTahunan);