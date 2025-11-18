// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Perhitungan Kompensasi PHK", {
    // 	refresh(frm) {

    // 	},
    ssa(frm) {
        fetchTableSeym(frm);
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
    if (!frm.doc.ssa || !frm.doc.dphk) {
        return
    }
    frm.call('fetch_perhitungan', { throw_if_missing: true })
        .then(r => {
            if (r.message) {
                let linked_doc = r.message;
                // do something with linked_doc

            }
        })
}