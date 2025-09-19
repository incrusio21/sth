// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Rencana Kerja Harian", {
	refresh(frm) {
        frm.set_df_property("material", "cannot_add_rows", true);
        frm.set_df_property("kendaraan", "cannot_add_rows", true);
        frm.set_df_property("angkut", "cannot_add_rows", true);
	},
    target_volume(frm) {
        frm.doc.qty_tenaga_kerja = frm.doc.volume_basis ? flt(frm.doc.target_volume / frm.doc.volume_basis) : 0
	},
    kode_kegiatan(frm){
        frm.set_value("blok", "")
        frm.set_value("batch", "")
    }
});

sth.plantation.RencanaKerjaHarian = class RencanaKerjaHarian extends sth.plantation.TransactionController {
    setup(doc) {
        super.setup(doc)

        for (const fieldname of ["target_volume"]) {
            frappe.ui.form.on(doc.doctype, fieldname, function(doc, cdt, cdn) {
                me.calculate_total(cdt, cdn, "material")
            });
        }

        for (const fieldname of ["qty_tenaga_kerja"]) {
            frappe.ui.form.on(doc.doctype, fieldname, function(doc, cdt, cdn) {
                me.calculate_total(cdt, cdn)
            });
        }

        let me = this
        for (const fieldname of ["kode_kegiatan", "tipe_kegiatan", "divisi", "is_bibitan", "blok", "batch", "posting_date"]) {
            frappe.ui.form.on(doc.doctype, fieldname, function() {
                me.get_rkb_data()
            });
        }
    }

    dosis(_, cdt, cdn){
        this.calculate_total(cdt, cdn)
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

    update_rate_or_qty_value(item){
        if(item.parentfield == "material"){
            item.qty = flt(item.dosis / this.frm.doc.target_volume)
        }
    }

    before_calculate_grand_total(){
		let qty = this.frm.doc.tipe_kegiatan == "Panen"  ? this.frm.doc.target_volume : this.frm.doc.qty_tenaga_kerja
        this.frm.doc.kegiatan_amount = flt(this.frm.doc.rate_basis * qty)
    }

    get_rkb_data(){
        let me = this
        let doc = this.frm.doc
        if (
            !(doc.kode_kegiatan && doc.tipe_kegiatan && doc.divisi && doc.posting_date) ||
            (doc.is_bibitan && !doc.batch) ||
            (!doc.is_bibitan && !doc.blok)
        ) return;

        frappe.call({
            method: "sth.plantation.doctype.rencana_kerja_harian.rencana_kerja_harian.get_rencana_kerja_bulanan",
            args: {
                kode_kegiatan: doc.kode_kegiatan,
                tipe_kegiatan: doc.tipe_kegiatan,
                divisi: doc.divisi,
                blok: doc.is_bibitan ? doc.batch : doc.blok,
                posting_date: doc.posting_date,
                is_bibitan: doc.is_bibitan,
            },
            freeze: true,
            callback: function (data) {
                me.frm.set_value(data.message)
            }
        })
    }
}

cur_frm.script_manager.make(sth.plantation.RencanaKerjaHarian);
