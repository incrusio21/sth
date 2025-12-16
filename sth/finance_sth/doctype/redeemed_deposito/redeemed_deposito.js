// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt
frappe.provide('sth.finance_sth');
sth.finance_sth.RedeemedDeposito = class RedeemedDeposito extends sth.plantation.AccountsController {
    refresh() {
        this.show_general_ledger()
    }
}

cur_frm.script_manager.make(sth.finance_sth.RedeemedDeposito);
// frappe.ui.form.on("Redeemed Deposito", {
// 	refresh(frm) {

// 	},
// });
