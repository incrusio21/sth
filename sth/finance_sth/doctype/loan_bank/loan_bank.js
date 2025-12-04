// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Loan Bank", {
	refresh(frm) {
        filterBankAccount(frm)
	},
});

function filterBankAccount(frm) {
    frm.set_query('bank_account', () => {
        return{
            filters: {
                bank: frm.doc.bank
            }
        }
    })
}