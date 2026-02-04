// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt
frappe.ui.form.on("Dividen", {
	refresh(frm) {
        setFilterOne(frm)
        setFilterTwo(frm)
        make_payment_entry(frm)
	},
    company_one(frm){
        setFilterOne(frm)
        setAccountCompanyOne(frm)
    },
    unit_one(frm){
        setFilterOne(frm)
    },
    company_two(frm){
        setFilterTwo(frm)
        setAccountCompanyTwo(frm)
    },
    unit_two(frm){
        setFilterTwo(frm)
    }
});

function setFilterOne(frm) {
    frm.set_query("unit_one", (doc)=>{
        return {
            filters:{
                company: doc.company_one,
                ho: 1
            }
        }
    })
    frm.set_query('bank_one', (doc)=>{
        return{
            filters:{
                company: ["=", doc.company_one]
            }
        }
    })
    frm.set_query("bank_account_one", (doc)=>{
        return {
            filters:{
                company: doc.company_one,
                unit: doc.unit_one,
                bank: doc.bank_one
            }
        }
    })
}

function setFilterTwo(frm) {
    frm.set_query("unit_two", (doc)=>{
        return {
            filters:{
                company: doc.company_two,
                ho: 1
            }
        }
    })
    frm.set_query('bank_two', (doc)=>{
        return{
            filters:{
                company: ["=", doc.company_two]
            }
        }
    })
    frm.set_query("bank_account_two", (doc)=>{
        return {
            filters:{
                company: doc.company_two,
                unit: doc.unit_two,
                bank: doc.bank_two
            }
        }
    })
}

async function setAccountCompanyOne(frm){
    const resCompany = await frappe.db.get_value("Company", frm.doc.company_one, ["default_dividen_payable_account", "default_dividen_equity_account"])
    
    frm.set_value("payable_account", resCompany.message.default_dividen_payable_account)
    frm.set_value("equity_account", resCompany.message.default_dividen_equity_account)
    frm.refresh_field("payable_account")
    frm.refresh_field("equity_account")
}

async function setAccountCompanyTwo(frm){
    const resCompany = await frappe.db.get_value("Company", frm.doc.company_two, ["default_dividen_receivale_account", "default_dividen_income_account"])
    
    frm.set_value("receivable_account", resCompany.message.default_dividen_receivale_account)
    frm.set_value("income_account", resCompany.message.default_dividen_income_account)
    frm.refresh_field("receivable_account")
    frm.refresh_field("income_account")
}

function make_payment_entry(frm) {
    if (!frm.doc.payment_entry_sent && frm.doc.docstatus == 1) {
        frm.add_custom_button('Payment', () => {
            frappe.call({
            method: "sth.finance_sth.doctype.dividen.dividen.make_payment_entry",
            args: {source_name: frm.doc.name, type:"Sent"},
            }).then(r => {
                frappe.model.sync(r.message);
                frappe.set_route("Form", r.message.doctype, r.message.name);
            })
        }, 'Create');
    }

    if (!frm.doc.payment_entry_receive && frm.doc.docstatus == 1) {        
        frm.add_custom_button('Receive', () => {
            frappe.call({
            method: "sth.finance_sth.doctype.dividen.dividen.make_payment_entry",
            args: {source_name: frm.doc.name, type:"Receive"},
            }).then(r => {
                frappe.model.sync(r.message);
                frappe.set_route("Form", r.message.doctype, r.message.name);
            })
        }, 'Create');
    }
}
