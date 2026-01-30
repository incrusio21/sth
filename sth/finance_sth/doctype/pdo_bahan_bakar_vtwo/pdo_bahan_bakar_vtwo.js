// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt
frappe.provide('sth.finance_sth');

frappe.ui.form.on("PDO Bahan Bakar Vtwo", {
	refresh(frm) {
        // frm.disable_save();
	},
});

sth.finance_sth.PDOBahanBakarVtwo = class PDOBahanBakarVtwo extends sth.plantation.AccountsController {
    refresh() {
        this.show_general_ledger()
    }
}

cur_frm.script_manager.make(sth.finance_sth.PDOBahanBakarVtwo);