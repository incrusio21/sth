// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Perhitungan Kompensasi PHK", {
// 	refresh(frm) {

// 	},
// });

sth.plantation.PerhitunganKaryawanPHK = class PerhitunganKaryawanPHK extends sth.plantation.AccountsController {
    refresh() {
        this.show_general_ledger()
    }
}

cur_frm.script_manager.make(sth.plantation.PerhitunganKaryawanPHK);