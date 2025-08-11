// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

sth.plantation.setup_budget_controller()

frappe.ui.form.on("Budget Traksi Tahunan", {
	refresh(frm) {

	},
    total_km_hm(frm){
        frm.set_value("rp_kmhm", flt(frm.doc.grand_total / frm.doc.total_km_hm, precision("rp_kmhm", frm.doc)))
    }
});

sth.plantation.BudgetTraksiTahunan = class BudgetTraksiTahunan extends sth.plantation.BudgetController {
    refresh(doc) {
        super.refresh(doc)
    }

    after_calculate_grand_total(){
        this.frm.doc.rp_kmhm = flt(
            this.frm.doc.grand_total / this.frm.doc.total_km_hm, 
            precision("rp_kmhm", this.frm.doc)
        );
    }
}

cur_frm.script_manager.make(sth.plantation.BudgetTraksiTahunan);