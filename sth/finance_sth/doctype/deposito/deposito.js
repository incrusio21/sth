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
    const monthDays = frm.doc.month_days;

    const diffDay = frappe.datetime.get_day_diff(endDate, startDate) + 1
    const month = Math.floor(diffDay / monthDays);
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
    const monthDays = frm.doc.month_days;
    
    if (!interest || !tax || !depositAmount || !startDate || !endDate) {
        return
    }

    const diffDay = frm.doc.tenor
    const interestAmount = depositAmount * interest * (diffDay*monthDays) /yearDays;
    const interestAmountMonthly = depositAmount * interest *monthDays /yearDays;
    const taxAmount = interestAmount * tax;
    const taxAmountMonthly = interestAmountMonthly * tax;
    const total = interestAmount - taxAmount;
    const totalMonthly = interestAmountMonthly - taxAmountMonthly;

    frm.set_value("interest_amount", interestAmount)
    frm.set_value("tax_amount", taxAmount)
    frm.set_value("total", total)
    frm.set_value("interest_amount_monthly", interestAmountMonthly)
    frm.set_value("tax_amount_monthly", taxAmountMonthly)
    frm.set_value("total_monthly", totalMonthly)
    frm.set_value("grand_total", total)
    frm.set_value("outstanding_amount", total)
    frm.refresh_field("interest_amount")
    frm.refresh_field("tax_amount")
    frm.refresh_field("total")
    frm.refresh_field("interest_amount_monthly")
    frm.refresh_field("tax_amount_monthly")
    frm.refresh_field("total_monthly")
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

    frappe.db.get_value("Company", frm.doc.company, "*")
    .then(r => {
        if (frm.is_new()) {
            frm.set_value('debit_to', r.message.default_deposito_debit_account)
            frm.set_value('expense_account', r.message.default_deposito_expense_account)
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