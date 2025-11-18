// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Perhitungan Kompensasi PHK", {
    async ssa(frm) {
        ssa = await frappe.db.get_doc("Salary Structure Assignment", frm.doc.ssa);

        if (ssa) {
            frm.set_query("exit_interview", function () {
                return {
                    filters: [["Exit Interview", "employee", "=", ssa.employee]]
                };
            });
        }
    }
});

sth.plantation.PerhitunganKaryawanPHK = class PerhitunganKaryawanPHK extends sth.plantation.AccountsController {
    refresh() {
        this.show_general_ledger()
    }
}

cur_frm.script_manager.make(sth.plantation.PerhitunganKaryawanPHK);