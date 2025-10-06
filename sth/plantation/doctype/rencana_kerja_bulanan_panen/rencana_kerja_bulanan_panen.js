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
        this.kegiatan_fetch_fieldname = ["volume_basis", "rupiah_basis"]

        let me = this
        for (const fieldname of ["akp", "volume_basis", "jumlah_pokok", "bjr", "tonase","qty_basis", "upah_per_basis", "premi"]) {
            frappe.ui.form.on(doc.doctype, fieldname, function(doc, cdt, cdn) {
                me.calculate_total(cdt, cdn)
            });
        }
    }

    set_query_field(){
        super.set_query_field()
    
        this.frm.set_query("kegiatan", function(doc){
            return{
                filters: {
                    company: ["=", doc.company],
                    tipe_kegiatan: "Panen",
                }
            }
        })

    }

    calculate_amount_addons(){
        let doc = this.frm.doc
        
        doc.jumlah_janjang = flt(doc.jumlah_pokok * doc.akp)
        doc.tonase = flt(doc.jumlah_janjang * doc.bjr)
        if(!doc.jumlah_tenaga_kerja){
            doc.jumlah_tenaga_kerja = flt(doc.tonase / doc.volume_basis)
        }
        doc.total_upah = flt(doc.tonase * doc.upah_per_basis)
        doc.pemanen_amount = flt(doc.total_upah) + flt(doc.premi)
    }
}

cur_frm.script_manager.make(sth.plantation.RencanaKerjaBulananPanen);
