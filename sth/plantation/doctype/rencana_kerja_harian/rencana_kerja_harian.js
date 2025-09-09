// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Rencana Kerja Harian", {
// 	refresh(frm) {

// 	},
// });

sth.plantation.RencanaKerjaHarian = class RencanaKerjaBulananUmum extends sth.plantation.TransactionController {

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
            return{
                filters: {
                    company: doc.company,
                    is_group: 0
                }
            }
        })

    }

    get_rkb_data(){
        let doc = this.frm.doc
        if(!(doc.kode_kegiatan && doc.tipe_kegiatan && doc.divisi && doc.blok && doc.tanggal_transaksi)) return
        
        frappe.call({
            method: "sth.plantation.doctype.rencana_kerja_harian.rencana_kerja_harianget_rencana_kerja_bulanan",
            args: {
                kode_kegiatan: doc.kode_kegiatan,
                tipe_kegiatan: doc.tipe_kegiatan,
                divisi: doc.divisi,
                blok: doc.blok,
                tanggal_rkh: doc.tanggal_transaksi
            },
            freeze: true,
            callback: function (data) {
                
            }
        })
    }
}

cur_frm.script_manager.make(sth.plantation.RencanaKerjaHarian);
