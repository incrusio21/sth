// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.provide('sth.finance_sth');
sth.finance_sth.DepositoInterest = class DepositoInterest extends sth.plantation.AccountsController {
    refresh() {
        this.show_general_ledger()
    }
}

cur_frm.script_manager.make(sth.finance_sth.DepositoInterest);
// frappe.ui.form.on("Deposito Interest", {
// 	refresh(frm) {

// 	},
// });
