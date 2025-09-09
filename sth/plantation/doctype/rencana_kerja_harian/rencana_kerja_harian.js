// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Rencana Kerja Harian", {
	refresh(frm) {
        frm.set_df_property("material", "cannot_add_rows", true);
	},
    target_volume(frm) {
        frm.doc.qty_tenaga_kerja = frm.doc.volume_basis ? flt(frm.doc.target_volume / frm.doc.volume_basis) : 0
        if(frm.doc.target_volume){
            frm.doc.material.forEach(item => {
                item.qty = flt(item.dosis / frm.doc.target_volume)
            })
        }
        frm.doc.kegiatan_amount = flt(frm.doc.rate_basis * frm.doc.target_volume)
        cur_frm.cscript.calculate_grand_total()

        frm.refresh_fields()
	},
});

frappe.ui.form.on("Detial RKH Material", {
	dosis(frm, cdt, cdn) {
        if(!frm.doc.target_volume) return

        let item = locals[cdt][cdn]
        frappe.model.set_value(cdt, cdn, "qty", item.dosis / frm.doc.target_volume)
	},
});

sth.plantation.RencanaKerjaHarian = class RencanaKerjaBulananUmum extends sth.plantation.TransactionController {
    setup(doc) {
        super.setup(doc)

        let me = this
        for (const fieldname of ["kode_kegiatan", "tipe_kegiatan", "divisi", "blok", "tanggal_transaksi"]) {
            frappe.ui.form.on(doc.doctype, fieldname, function() {
                me.get_rkb_data()
            });
        }
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
            return{
                filters: {
                    company: doc.company,
                    is_group: 0
                }
            }
        })

    }

    get_rkb_data(){
        let me = this
        let doc = this.frm.doc
        if(!(doc.kode_kegiatan && doc.tipe_kegiatan && doc.divisi && doc.blok && doc.tanggal_transaksi)) return
        
        frappe.call({
            method: "sth.plantation.doctype.rencana_kerja_harian.rencana_kerja_harian.get_rencana_kerja_bulanan",
            args: {
                kode_kegiatan: doc.kode_kegiatan,
                tipe_kegiatan: doc.tipe_kegiatan,
                divisi: doc.divisi,
                blok: doc.blok,
                tanggal_rkh: doc.tanggal_transaksi
            },
            freeze: true,
            callback: function (data) {
                me.frm.set_value(data.message)
            }
        })
    }
}

cur_frm.script_manager.make(sth.plantation.RencanaKerjaHarian);
