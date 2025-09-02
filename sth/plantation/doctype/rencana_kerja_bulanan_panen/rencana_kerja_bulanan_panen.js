// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

sth.plantation.setup_rencana_kerja_controller()

frappe.ui.form.on("Rencana Kerja Bulanan Panen", {
	refresh(frm) {
        frm.add_fetch("blok", "last_bjr", "bjr");
	}
});

sth.plantation.RencanaKerjaBulananPanen = class RencanaKerjaBulananPanen extends sth.plantation.RencanaKerjaController {
    setup(doc) {
        super.setup(doc)

        this.update_field_duplicate = [
            {
                fieldtype: "Float",
                fieldname: "last_bjr",
                in_list_view: 1,
                label: __("BJR")
            }
        ]
        
        this.fieldname_duplicate_edit = {"last_bjr": "bjr"}

        let me = this
        for (const fieldname of ["akp", "jumlah_pokok", "bjr", "tonase","qty_basis", "upah_per_basis", "premi"]) {
            frappe.ui.form.on(doc.doctype, fieldname, function(doc, cdt, cdn) {
                me.calculate_total(cdt, cdn)
            });
        }
    }

    set_query_field(){
        super.set_query_field()
    
        this.frm.set_query("kode_kegiatan", function(doc){
            return{
                filters: {
                    company: doc.company,
                    tipe_kegiatan: "Panen",
                    is_group: 0
                }
            }
        })

    }

    calculate_amount_addons(){
        let doc = this.frm.doc
        
        doc.jumlah_janjang = flt(doc.jumlah_pokok * doc.akp)
        doc.tonase = flt(doc.jumlah_janjang * doc.bjr)
        doc.total_upah = doc.upah_per_basis ? flt(doc.tonase / doc.upah_per_basis) : 0
        doc.pemanen_amount = flt(doc.total_upah) + flt(doc.premi)
    }
}

cur_frm.script_manager.make(sth.plantation.RencanaKerjaBulananPanen);
