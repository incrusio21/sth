// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

sth.plantation.setup_bkm_controller()

frappe.ui.form.on("Buku Kerja Mandor Perawatan", {
    refresh(frm) {

    },
    kategori_kegiatan(frm) {
        frm.set_value({"blok": "", "batch": ""})
    },
});

sth.plantation.BukuKerjaMandorPerawatan = class BukuKerjaMandorPerawatan extends sth.plantation.BKMController {
    setup(doc) {
        super.setup(doc)
               
        this.fieldname_total.push("premi_amount")
        this.kegiatan_fetch_fieldname.push("have_premi", "min_basis_premi", "rupiah_premi")

        this.get_data_rkh_field.push("batch")
        this.hasil_kerja_update_field.push("have_premi", "min_basis_premi", "rupiah_premi")

        this.setup_bkm(doc)
    }

    set_query_field() {
        super.set_query_field()

        this.frm.set_query("kategori_kegiatan", function () {
            return {
                filters: {
                    is_perawatan: 1
                }
            }
        })

        this.frm.set_query("kegiatan", function (doc) {
            return {
                filters: {
                    kategori_kegiatan: ["=", doc.kategori_kegiatan],
                    company: ["=", doc.company],
                }
            }
        })

        this.frm.set_query("item", "material", function (doc) {
            return {
                query: 'sth.controllers.queries.material_kegiatan_query',
                filters: {
                    kegiatan: ["=", doc.kegiatan],
                }
            }
        })

    }

    update_rate_or_qty_value(item) {
        if (item.parentfield != "hasil_kerja") return

        let doc = this.frm.doc
        
        item.rate = item.rate || this.frm.doc.rupiah_basis
        item.hari_kerja = flt(item.qty / doc.volume_basis)

        if (doc.have_premi & item.hari_kerja > 1){
            item.hari_kerja =  1
            if (doc.persentase_premi && item.qty >= doc.min_basis_premi) {
                item.premi_amount = doc.rupiah_premi
            }
        }
    }

    update_value_after_amount(item) {
        item.sub_total = flt(item.amount) + flt(item.premi_amount)
    }
}

cur_frm.script_manager.make(sth.plantation.BukuKerjaMandorPerawatan);
