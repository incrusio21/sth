// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Installment Loan", {
// 	refresh(frm) {

// 	},
// });

frappe.provide('sth.finance_sth');
sth.finance_sth.InstallmentLoan = class InstallmentLoan extends sth.plantation.AccountsController {
    refresh() {
        this.show_general_ledger()
    }
}

cur_frm.script_manager.make(sth.finance_sth.InstallmentLoan);
