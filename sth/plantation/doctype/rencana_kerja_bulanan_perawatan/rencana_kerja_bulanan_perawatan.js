// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

sth.plantation.setup_rencana_kerja_controller()

frappe.ui.form.on("Rencana Kerja Bulanan Perawatan", {
	refresh(frm) {
        
	},
    kategori_kegiatan(frm){
        frm.set_value("blok", "")
        frm.set_value("batch", "")
    }
});

sth.plantation.RencanaKerjaBulananPerawatan = class RencanaKerjaBulananPerawatan extends sth.plantation.RencanaKerjaController {
    setup(doc) {
        super.setup(doc)

        let me = this
        for (const fieldname of ["qty_basis", "upah_per_basis", "premi"]) {
            frappe.ui.form.on(doc.doctype, fieldname, function(doc, cdt, cdn) {
                me.calculate_total(cdt, cdn)
            });
        }
    }

    set_query_field(){
        super.set_query_field()
        
        this.frm.set_query("kategori_kegiatan", function(){
		    return{
		        filters: {
                    is_perawatan: 1
                }
		    }
		})

        this.frm.set_query("kode_kegiatan", function(doc){
            if(!(doc.company && doc.kategori_kegiatan)){
                frappe.throw("Please Select Kategori Kegiata and Company First")
            }

		    return{
		        filters: {
                    is_group: 0,
                    kategori_kegiatan: doc.kategori_kegiatan,
                    company: doc.company
                }
		    }
		})

        this.frm.set_query("batch", function(doc){
		    return{
		        filters: {
                    company: doc.company
                }
		    }
		})


    }

    calculate_amount_addons(){
        let doc = this.frm.doc

        doc.jumlah_tenaga_kerja = doc.qty_basis ? flt(doc.qty / doc.qty_basis) : 0
        doc.tenaga_kerja_amount = flt(doc.jumlah_tenaga_kerja * doc.upah_per_basis) + flt(doc.premi)
    }
}

cur_frm.script_manager.make(sth.plantation.RencanaKerjaBulananPerawatan);