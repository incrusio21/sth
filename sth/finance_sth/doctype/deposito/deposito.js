// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt
frappe.provide('sth.finance_sth');
sth.finance_sth.Deposito = class Deposito extends sth.plantation.AccountsController {
    refresh() {
        this.show_general_ledger()
    }
}

cur_frm.script_manager.make(sth.finance_sth.Deposito);

frappe.ui.form.on("Deposito", {
	refresh(frm) {
        filterBankAccount(frm)
        filterAccount(frm)
        filterUnit(frm)
	},
    value_date(frm){
        calculateTenor(frm) 
    },
    maturity_date(frm){
        calculateTenor(frm) 
    },
    interest(frm){
        calculateDeposito(frm)
    },
    tax(frm){
        calculateDeposito(frm)
    },
    deposit_amount(frm){
        calculateDeposito(frm)
    }
});

function filterBankAccount(frm) {
    frm.set_query('bank_account', (doc) => {
        return {
            filters:{
                company: ["=", doc.company],
                bank: ["=", doc.bank]
            }
        }
    })
}

function calculateTenor(frm) {
    const startDate = frm.doc.value_date;
    const endDate = frm.doc.maturity_date;
    
    const diffDay = frappe.datetime.get_day_diff(endDate, startDate) + 1
    const month = Math.floor(diffDay / 30);
    frm.set_value('tenor', month)
    frm.refresh_field('tenor')

    calculateDeposito(frm)
}

function calculateDeposito(frm) {
    const interest = frm.doc.interest / 100;
    const tax = frm.doc.tax / 100;
    const depositAmount = frm.doc.deposit_amount;
    const startDate = frm.doc.value_date;
    const endDate = frm.doc.maturity_date;
    const yearDays = frm.doc.year_days;
    if (!interest || !tax || !depositAmount || !startDate || !endDate) {
        return
    }

    const diffDay = frm.doc.tenor
    const interestAmount = depositAmount * diffDay * interest/yearDays;
    const taxAmount = interestAmount * tax;
    const total = interestAmount - taxAmount;

    frm.set_value("interest_amount", interestAmount)
    frm.set_value("tax_amount", taxAmount)
    frm.set_value("total", total)
    frm.set_value("grand_total", total)
    frm.set_value("outstanding_amount", total)
    frm.refresh_field("interest_amount")
    frm.refresh_field("tax_amount")
    frm.refresh_field("total")
    frm.refresh_field("grand_total")
    frm.refresh_field("outstanding_amount")
}

function filterAccount(frm) {
    frm.set_query("debit_to", (doc) => {
        return {
            filters: {
                account_type: "Receivable",
                company: doc.company
            }
        }
    })
    frm.set_query("expense_account", (doc) => {
        return {
            filters: {
                account_type: ["!=","Receivable"],
                company: doc.company
            }
        }
    })
}

function filterUnit(frm) {
    frm.set_query("unit", (doc) => {
        return {
            filters: {
                company: ["=",doc.company]
            }
        }
    })
}