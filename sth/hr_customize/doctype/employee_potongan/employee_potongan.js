// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.provide("sth.hr_customize")

frappe.ui.form.on("Employee Potongan", {
    refresh(frm) {
        frm.set_df_property("details", "cannot_add_rows", true);
        frm.set_query("unit", function () {
            return {
                filters: {
                    company: ["=", frm.doc.company]
                }
            };
        });

        frm.set_query("bank_account", function () {
            return {
                filters: {
                    company: ["=", frm.doc.company],
                    unit: ["=", frm.doc.unit],
                }
            };
        });
        createPayment(frm);
    },
});

function createPayment(frm) {
    if (frm.doc.docstatus == 1 && frm.doc.outstanding_amount > 0) {
        frm.add_custom_button('Payment', () => {
            frappe.model.open_mapped_doc({
                method: "sth.hr_customize.doctype.employee_potongan.employee_potongan.make_payment_entry",
                frm: frm,
            })
        }, 'Create');
    }
}

sth.hr_customize.EmployeePotongan = class EmployeePotongan extends sth.plantation.AccountsController {
    setup() {
        let me = this

        for (const fieldname of ["rate"]) {
            frappe.ui.form.on('Employee Potongan Details', fieldname, function (doc, cdt, cdn) {
                me.calculate_total(cdt, cdn)
            });
        }
    }

    refresh() {
        this.show_general_ledger()
        this.set_query_field()
    }

    // company() {
    //     this.get_accounts()
    // }

    jenis_potongan() {
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

    get_accounts() {
        let me = this

        frappe.call({
            method: "sth.hr_customize.doctype.employee_potongan.employee_potongan.fetch_company_account",
            args: {
                company: me.frm.doc.company,
                jenis_potongan: me.frm.doc.jenis_potongan,
            },
            callback: function (r) {
                console.log(r.message);
                if (!r.exc && r.message) {
                    me.frm.set_value(r.message);
                    me.frm.refresh_fields("credit_to");
                    me.frm.refresh_fields("expense_account");
                }
            }
        });
    }

    calculate_total() {
        let totals = 0
        for (const item of this.frm.doc.details || []) {
            totals += flt(item.rate)
        }

        this.frm.doc.grand_total = totals
        this.frm.refresh_fields()
    }
}

cur_frm.script_manager.make(sth.hr_customize.EmployeePotongan);