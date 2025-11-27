// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.provide("sth.legal");

// frappe.ui.form.on("Pengajuan Pembayaran", {
// 	refresh(frm) {

// 	},
// });

sth.legal.PengajuanPembayaran = class PengajuanPembayaran extends sth.plantation.AccountsController {
    setup() {
        let me = this

        for (const fieldname of ["amount"]) {
            frappe.ui.form.on('Pengajuan Pembayaran Details', fieldname, function (doc, cdt, cdn) {
                me.calculate_total(cdt, cdn)
            });
        }
    }
    
    refresh() {
        this.show_general_ledger()
        this.set_query_field()
    }

    company() {
        this.get_accounts()
    }

    set_query_field() {
        this.frm.set_query("expense_account", function (doc) {
            return {
                filters: {
                    root_type: "Expense",
                    company: ["=", doc.company],
                    is_group: 0,
                    disabled: 0,
                }
            }
        })

        this.frm.set_query("credit_to", function (doc) {
            return {
                filters: {
                    account_type: "Payable",
                    company: ["=", doc.company],
                    is_group: 0,
                    disabled: 0,
                }
            }
        })
    }

    get_accounts(){
        let me = this

        frappe.call({
            method: "sth.legal.doctype.pengajuan_pembayaran.pengajuan_pembayaran.fetch_company_account",
            args: {
                company: me.frm.doc.company
            },
            callback: function(r) {
                if(!r.exc && r.message) {
                    me.frm.set_value(r.message);
                }
            }
        });
    }

    calculate_total(){
        let totals = 0
        for (const item of this.frm.doc.details || []) {
            totals += flt(item.amount)
        }

        this.frm.doc.grand_total = totals
        this.frm.refresh_fields()
    }
}

cur_frm.script_manager.make(sth.legal.PengajuanPembayaran);
