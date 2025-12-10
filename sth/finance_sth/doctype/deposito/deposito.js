// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt
// frappe.provide('sth.finance_sth');
// sth.finance_sth.Deposito = class Deposito extends sth.plantation.AccountsController {
//     refresh() {
//         this.show_general_ledger()
//     }
// }

// cur_frm.script_manager.make(sth.finance_sth.Deposito);

frappe.ui.form.on("Deposito", {
	refresh(frm) {
        // filterBankAccount(frm)
        // filterAccount(frm)
        // filterUnit(frm)

	},
    value_date(frm){
        // calculateTenor(frm)
        getMaturityDate(frm);
    },
    tenor(frm){
        getMaturityDate(frm);
    },
    interest(frm){
        // calculateDeposito(frm)
    },
    tax(frm){
        // calculateDeposito(frm)
    },
    deposit_amount(frm){
        // calculateDeposito(frm)
    }
});

frappe.ui.form.on("Deposito Interest Table", {
    create_payment(frm, cdt, cdn){
        makePaymentEntry(frm, cdt, cdn)
    }
})

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

function filterUnit(frm) {
    frm.set_query("unit", (doc) => {
        return {
            filters: {
                company: ["=",doc.company]
            }
        }
    })
}

function getMaturityDate(frm) {
    let valueDate = frm.doc.value_date;
    let tenor = frm.doc.tenor;

    if (!valueDate || !tenor) {
        return
    }

    let maturityDate = frappe.datetime.add_months(valueDate, tenor);
    frm.set_value('maturity_date', maturityDate)
    frm.refresh_field('maturity_date')
}

function makePaymentEntry(frm, cdt, cdn) {
    const curRow = locals[cdt][cdn];
    if (curRow.payment) {
        frappe.throw(`Payment Receive untuk Bunga Deposito Row:${curRow.idx} ini sudah dibuat`)
    }
    frappe.call({
        method: "sth.finance_sth.doctype.deposito.deposito.make_payment_entry",
        args: {source_name: curRow.deposito_interest},
    }).then(r => {
        frappe.model.sync(r.message);
        frappe.set_route("Form", r.message.doctype, r.message.name);
    })

}