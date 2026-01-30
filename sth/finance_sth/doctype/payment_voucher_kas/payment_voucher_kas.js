// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.provide('sth.finance_sth');
sth.finance_sth.PaymentVoucherKas = class PaymentVoucherKas extends sth.plantation.AccountsController {
    refresh() {
        this.show_general_ledger()
    }
}
cur_frm.script_manager.make(sth.finance_sth.PaymentVoucherKas);

frappe.ui.form.on("Payment Voucher Kas", {
	refresh(frm) {
        setDefaultAccount(frm)
        defaultInternal(frm)
        filterUnit(frm)
        filterAccount(frm)
	},
    company(frm){
        setDefaultAccount(frm)
        filterUnit(frm)
        filterAccount(frm)
    },
    currency(frm){
        setCurrencyExchange(frm)
    },
    payment_amount(frm){
        setTotal(frm)
    }
});




async function setDefaultAccount(frm) {
    const resCompany = await frappe.db.get_value("Company", frm.doc.company, "*");

    if (!resCompany) {
        return
    }

    frm.set_value("debit_to", resCompany.message.default_kas_receivable_account);
    frm.set_value("credit_to", resCompany.message.default_kas_payable_account);
    frm.set_value("currency", resCompany.message.default_currency);
    frm.refresh_field("debit_to");
    frm.refresh_field("credit_to");
    frm.refresh_field("currency");
}

async function defaultInternal(frm) {
    const internalEmployee = await frappe.db.get_single_value("Payment Settings", "internal_employee")
    const customerReceivable = await frappe.db.get_single_value("Payment Settings", "receivable_customer")

    frm.set_value("employee", internalEmployee);
    frm.set_value("customer", customerReceivable);
    frm.refresh_field("employee");
    frm.refresh_field("customer");
}

function filterUnit(frm) {
    frm.set_query("unit", (doc) => {
        return{
            filters: {
                company: doc.company
            }
        }
    })
}

function filterAccount(frm) {
    frm.set_query("account", (doc) => {
        return{
            filters: {
                company: doc.company,
                is_group: 0,
                account_type: "Indirect Expense"
            }
        }
    })
}

function setCurrencyExchange(frm) {
    if (!frm.doc.currency) {
        return
    }
    frm.call("set_exchange_rate")
    .then(r => {
        if (r.message) {
            let linked_doc = r.message;
            // do something with linked_doc
        }
    })
}

function setTotal(frm) {
    frm.set_value("grand_total", frm.doc.payment_amount);
    frm.set_value("outstanding_amount", frm.doc.payment_amount);
    frm.refresh_field("grand_total");
    frm.refresh_field("outstanding_amount");
}