// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

sth.plantation.setup_budget_controller()

// frappe.ui.form.on("Budget Biaya Umum Tahunan", {
// 	refresh(frm) {

// 	},
// });

sth.plantation.BudgetBiayaUmumTahunan = class BudgetBiayaUmumTahunan extends sth.plantation.BudgetController {

}

cur_frm.script_manager.make(sth.plantation.BudgetBiayaUmumTahunan);
