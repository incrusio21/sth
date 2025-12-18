// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.provide('sth.finance_sth');
sth.finance_sth.DividenTransaction = class DividenTransaction extends sth.plantation.AccountsController {
    refresh() {
        this.show_general_ledger()
    }
}

cur_frm.script_manager.make(sth.finance_sth.DividenTransaction);
// frappe.ui.form.on("Dividen Transaction", {
// 	refresh(frm) {

// 	},
// });
