// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

sth.plantation.setup_rencana_kerja_controller()

// frappe.ui.form.on("Rencana Kerja Bulanan Support", {
// 	refresh(frm) {

// 	},
// });

sth.plantation.RencanaKerjaBulananSupport = class RencanaKerjaBulananSupport extends sth.plantation.RencanaKerjaController {
    setup(doc) {
        super.setup(doc)

        let me = this
        for (const fieldname of ["ump_harian"]) {
            frappe.ui.form.on(doc.doctype, fieldname, function(doc, cdt, cdn) {
                me.calculate_total(cdt, cdn, "pegawai")
            });
        }
    }

    estimasi_gaji(_, cdt, cdn){
        this.calculate_total(cdt, cdn)
    }

    update_rate_or_qty_value(item){
        item.rate = this.frm.doc.ump_harian
    }

    update_value_after_amount(item){
        super.update_value_after_amount(item)

        item.amount = flt(item.amount + (item.estimasi_gaji || 0), precision("amount", item));
    }
}

cur_frm.script_manager.make(sth.plantation.RencanaKerjaBulananSupport);