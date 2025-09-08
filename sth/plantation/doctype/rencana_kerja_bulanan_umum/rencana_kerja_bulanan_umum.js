// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

sth.plantation.setup_rencana_kerja_controller()

// frappe.ui.form.on("Rencana Kerja Bulanan Umum", {
// 	refresh(frm) {

// 	},
// });

sth.plantation.RencanaKerjaBulananUmum = class RencanaKerjaBulananUmum extends sth.plantation.RencanaKerjaController {
    setup(doc) {
        super.setup(doc)

        let me = this
        for (const fieldname of ["ump_harian"]) {
            frappe.ui.form.on(doc.doctype, fieldname, function(doc, cdt, cdn) {
                me.calculate_total(cdt, cdn, "pegawai")
            });
        }
    }

    set_query_field(){
        super.set_query_field()
    
        this.frm.set_query("kode_kegiatan", function(doc){
            return{
                filters: {
                    company: doc.company,
                    tipe_kegiatan: "Biaya Umum",
                    is_group: 0
                }
            }
        })

    }

    qty(doc, cdt, cdn){
        this.calculate_total(cdt, cdn)

        if(cdt == "RKB Umum Pegawai" && doc.volume_basis){
            let item = locals[cdt][cdn]
            frappe.model.set_value(cdt, cdn, "jumlah_hk", item.qty / doc.volume_basis)
        }
    }

    premi(_, cdt, cdn){
        this.calculate_total(cdt, cdn)
    }

    update_rate_or_qty_value(item){
        item.rate = this.frm.doc.ump_harian
    }

    update_value_after_amount(item){
        super.update_value_after_amount(item)

        item.amount = flt(item.amount + (item.premi || 0), precision("amount", item));
    }
}

cur_frm.script_manager.make(sth.plantation.RencanaKerjaBulananUmum);