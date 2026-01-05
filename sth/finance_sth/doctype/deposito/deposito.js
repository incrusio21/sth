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
        frm.ignore_doctypes_on_cancel_all = ["Deposito Interest", "Payment Entry", "Redemeed Deposito"];
        filterBankAccount(frm)
        filterAccount(frm)
        filterUnit(frm)
        setAccount(frm)
        createPrincipalPayment(frm)
	},
    company(frm){
        setAccount(frm)
    },
    value_date(frm){
        // calculateTenor(frm)
        getMaturityDate(frm);
    },
    tenor(frm){
        getMaturityDate(frm);
    },
    redeemed(frm){
        makeRedeemedDeposito(frm)
    }
});

frappe.ui.form.on("Deposito Interest Table", {
    create_payment(frm, cdt, cdn){
        makePaymentEntry(frm, cdt, cdn)
    }
})

function filterBankAccount(frm) {
    frm.set_query('bank', (doc)=>{
        return{
            filters:{
                company: ["=", doc.company]
            }
        }
    })

    frm.set_query('bank_account', (doc) => {
        return {
            filters:{
                company: ["=", doc.company],
                bank: ["=", doc.bank],
                unit: ["=", doc.unit]
            }
        }
    })
}
function filterAccount(frm) {
    frm.set_query('credit_to', (doc) => {
        return {
            filters:{
                company: ["=", doc.company],
                is_group: ["=", 0],
                account_type: ["=", "Payable"]
            }
        }
    })
    frm.set_query('non_current_asset', (doc) => {
        return {
            filters:{
                company: ["=", doc.company],
                is_group: ["=", 0],
                account_type: ["=", "Non Current Asset"]
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
    if (frm.doc.payment_received) {
        frappe.throw(`Deposito sudah ditarik tidak bisa membuat Payment Receive`)
    }
    if (frm.doc.docstatus == 2) {
        frappe.throw(`Deposito sudah dicancel tidak bisa membuat Payment Receive`)
    }
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

async function setAccount(frm) {
    const resCompany = await frappe.db.get_value("Company", frm.doc.company, "*");
    
    frm.set_value('credit_to', resCompany.message.default_deposito_payable_account);
    frm.set_value('non_current_asset', resCompany.message.default_deposito_nca_account);
    frm.refresh_field('credit_to');
    frm.refresh_field('non_current_asset');
}

function createPrincipalPayment(frm) {
    let type = null
    if (frm.doc.docstatus == 1 && frm.doc.outstanding_amount > 0 && !frm.doc.payment_pay) {
        type = "Payment";
    }

    if (frm.doc.docstatus == 1 && frm.doc.outstanding_amount == 0 && frm.doc.is_redeemed == "Sudah" && !frm.doc.payment_received) {
        type = "Receive"
    }

    if (type == null) {
        return
    }
    frm.add_custom_button(type, () => {
        frappe.call({
            method: "sth.finance_sth.doctype.deposito.deposito.make_principal_payment",
            args: {source_name: frm.doc.name, type:type},
        }).then(r => {
            frappe.model.sync(r.message);
            frappe.set_route("Form", r.message.doctype, r.message.name);
        })
    }, 'Create');
}

function makeRedeemedDeposito(frm) {
    let today = moment().startOf('day');
    let maturity_date = moment(frm.doc.maturity_date, 'YYYY-MM-DD');

    if (maturity_date.isAfter(today)) {
        d.show();
    }else{
        frm.call('make_redemeed_deposito', { throw_if_missing: true })
        .then(r => {
            if (r.message) {
                let linked_doc = r.message;
                // do something with linked_doc
            }
        })

    }


}
let d = new frappe.ui.Dialog({
    title: 'Masukkan Jumlah Pinalti',
    fields: [
        {
            label: 'Pinalti',
            fieldname: 'pinalti',
            fieldtype: 'Currency'
        }
    ],
    size: 'small', // small, large, extra-large 
    primary_action_label: 'Submit',
    primary_action(values) {
        cur_frm.call('make_pinalti_deposito', { pinalti: values.pinalti })
        .then(r => {
            if (r.message) {
                let linked_doc = r.message;
                // do something with linked_doc
            }
        })
        d.hide();
    }
});