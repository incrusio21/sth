// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Perhitungan Kompensasi PHK", {
    refresh(frm) {
        frm.set_query("employee", function () {
            return {
                filters: {
                    relieving_date: ["is", "set"]
                }
            };
        });

        frm.ignore_doctypes_on_cancel_all = ["Exit Interview"]
        filterExitInterview(frm)
        setDefaultData(frm)
        // setDefaultSalaryComponent(frm)
        createPayment(frm)
    },
    employee(frm) {
        fetchSSA(frm);
    },
    dphk(frm) {
        fetchTableSeym(frm);
    }
});

sth.plantation.PerhitunganKaryawanPHK = class PerhitunganKaryawanPHK extends sth.plantation.AccountsController {
    refresh() {
        this.show_general_ledger()
    }
}

cur_frm.script_manager.make(sth.plantation.PerhitunganKaryawanPHK);

function fetchTableSeym(frm) {
    if (!frm.doc.dphk || !frm.doc.employee || !frm.doc.l_date || !frm.doc.exit_interview) {
        return
    }
    frm.call('fetch_perhitungan', { throw_if_missing: true })
        .then(r => {
            if (r.message) {
                let linked_doc = r.message;
            }
        })
}

function fetchSSA(frm) {
    if (!frm.doc.employee) {
        return
    }
    frm.call('fetch_ssa', { throw_if_missing: true })
        .then(r => {
            if (r.message) {
                let linked_doc = r.message;
            }
        })
}

function filterExitInterview(frm) {
    frm.set_query('exit_interview', () => {
        return {
            query: "sth.hr_customize.doctype.perhitungan_kompensasi_phk.perhitungan_kompensasi_phk.filter_exit_interview",
            filters: {
                employee: frm.doc.employee
            }
        }
    });
}

function setDefaultData(frm) {
    frm.call('fetch_default_data', { throw_if_missing: true })
        .then(r => {
            if (r.message) {
                let linked_doc = r.message;
            }
        })
}

function createPayment(frm) {
    if (frm.doc.docstatus == 1 && frm.doc.outstanding_amount > 0) {
        frm.add_custom_button('Payment', () => {
            frappe.model.open_mapped_doc({
                method: "sth.hr_customize.doctype.perhitungan_kompensasi_phk.perhitungan_kompensasi_phk.make_payment_entry",
                frm: frm,
            })
        }, 'Create');
    }
}