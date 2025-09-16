// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Buku Kerja Mandor Panen", {
// 	refresh(frm) {

// 	},
// });

sth.plantation.BukuKerjaMandorPerawatan = class BukuKerjaMandorPerawatan extends sth.plantation.TransactionController {
    setup(doc) {
        super.setup(doc)

        let me = this
    }

    set_query_field(){
        super.set_query_field()

        this.frm.set_query("blok", function(doc){
            if(!doc.divisi){
                frappe.throw("Please Select Divisi First")
            }

            return{
                filters: {
                    divisi: doc.divisi,
                }
            }
        })
        
        this.frm.set_query("kode_kegiatan", function(doc){
            if(!(doc.company)){
                frappe.throw("Please Select Kategori Kegiata and Company First")
            }

            return{
		        filters: {
                    is_group: 0,
                    tipe_kegiatan: "Panen",
                    company: doc.company
                }
		    }
        })

    }

    get_rkh_data(){
        let me = this
        let doc = this.frm.doc
        if(!(doc.kode_kegiatan && doc.divisi && doc.blok && doc.posting_date)) return
        
        frappe.call({
            method: "sth.plantation.doctype.buku_kerja_mandor_perawatan.buku_kerja_mandor_perawatan.get_rencana_kerja_harian",
            args: {
                kode_kegiatan: doc.kode_kegiatan,
                divisi: doc.divisi,
                blok: doc.blok,
                posting_date: doc.posting_date
            },
            freeze: true,
            callback: function (data) {
                me.frm.set_value(data.message)
            }
        })
    }
}

cur_frm.script_manager.make(sth.plantation.BukuKerjaMandorPerawatan);