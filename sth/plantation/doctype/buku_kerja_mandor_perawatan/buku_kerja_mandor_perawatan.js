// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Buku Kerja Mandor Perawatan", {
	refresh(frm) {

	},
    kategori_kegiatan(frm){
        frm.set_value("blok", "")
        frm.set_value("batch", "")
    }
});

sth.plantation.BukuKerjaMandorPerawatan = class BukuKerjaMandorPerawatan extends sth.plantation.TransactionController {
    setup(doc) {
        super.setup(doc)

        this.fieldname_total.push("qty", "hasil")

        let me = this
        for (const fieldname of ["hari_kerja", "volume_basis", "rp_per_basis"]) {
            frappe.ui.form.on(doc.doctype, fieldname, function(doc, cdt, cdn) {
                me.calculate_total(cdt, cdn, "hasil_kerja")
            });
        }

        for (const fieldname of ["kode_kegiatan", "divisi", "is_bibitan", "blok", "batch","posting_date"]) {
            frappe.ui.form.on(doc.doctype, fieldname, function() {
                me.get_rkh_data()
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

    }

    hasil(_, cdt, cdn){
        this.calculate_total(cdt, cdn)
    }

    update_rate_or_qty_value(item){
        if(item.parentfield == "hasil_kerja"){
            item.qty = flt(item.hasil / this.frm.doc.volume_basis)
            item.rate = item.rate ?? this.frm.doc.rp_per_basis
            
            if(this.frm.doc.per_premi && item.hari_kerja >= flt(this.frm.doc.volume_basis * ((1 + this.frm.doc.per_premi) / 100))){
                item.premi = this.frm.doc.rupiah_premi
            }
        }
    }

    after_calculate_item_values(table_name, total){
        if(table_name == "hasil_kerja"){
            this.frm.doc[`hari_kerja_total`] = flt(total["hari_kerja"] / data_table.length) || 0;
        }
    }

    get_rkh_data(){
        let me = this
        let doc = this.frm.doc
        if (
            !(doc.kode_kegiatan && doc.divisi && doc.posting_date) ||
            (doc.is_bibitan && !doc.batch) ||
            (!doc.is_bibitan && !doc.blok)
        ) return;
        
        frappe.call({
            method: "sth.controllers.queries.get_rencana_kerja_harian",
            args: {
                kode_kegiatan: doc.kode_kegiatan,
                divisi: doc.divisi,
                blok: doc.is_bibitan ? doc.batch : doc.blok,
                posting_date: doc.posting_date,
                is_bibitan: doc.is_bibitan
            },
            freeze: true,
            callback: function (data) {
                me.frm.set_value(data.message)
            }
        })
    }
}

cur_frm.script_manager.make(sth.plantation.BukuKerjaMandorPerawatan);
