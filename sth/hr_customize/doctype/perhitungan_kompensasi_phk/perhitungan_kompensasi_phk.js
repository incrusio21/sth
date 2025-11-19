// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Perhitungan Kompensasi PHK", {
    refresh(frm){
    },
    employee(frm) {
        fetchSSA(frm);
        fetchExitInterview(frm);
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
    if (!frm.doc.dphk) {
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
    frm.call('fetch_ssa', { throw_if_missing: true })
    .then(r => {
        if (r.message) {
            let linked_doc = r.message;
        }
    })
}

function fetchExitInterview(frm){
    frappe.db.get_value("Exit Interview", {
        "employee": frm.doc.employee, 
        "ref_doctype": frm.doc.doctype, 
        "reference_document_name": ["is", "not set"],
        "employee_status": "Exit Confirmed"
    }, "name").then(r => {
        frm.set_value('exit_interview', r.message.name)
        frm.refresh_field('exit_interview')
    })
}