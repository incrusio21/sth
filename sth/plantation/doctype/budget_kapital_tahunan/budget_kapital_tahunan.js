// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

sth.plantation.setup_budget_controller()

// frappe.ui.form.on("Budget Kapital Tahunan", {
// 	refresh(frm) {

// 	},
// });

sth.plantation.BudgetKapitalTahunan = class BudgetKapitalTahunan extends sth.plantation.BudgetController {

}

cur_frm.script_manager.make(sth.plantation.BudgetKapitalTahunan);